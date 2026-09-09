from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict

import typer
from rich.console import Console
from rich.table import Table

from .agent_runner import build_runner
from .config import Settings, load_settings
from .deep_read import DeepReadService
from .mcp_client import MCPError, ZoteroMCPClient
from .mkg_bridge import MKGBridge, SyncResult
from .research_embedding import OpenAICompatibleEmbeddingProvider
from .skill_loader import load_ljg_paper_skill
from .zotero_source import ZoteroPaperSource

app = typer.Typer(no_args_is_help=True, help="Zotero MCP × Meta Knowledge Graph bridge")
console = Console()


@contextmanager
def runtime() -> Iterator[tuple[Settings, ZoteroMCPClient, ZoteroPaperSource, MKGBridge]]:
    settings = load_settings()
    with ZoteroMCPClient(settings.zotero_mcp_url) as client:
        source = ZoteroPaperSource(client, settings.zotero_library_id)
        with MKGBridge(settings, source) as bridge:
            yield settings, client, source, bridge


def _runner(settings: Settings, name: str | None = None):
    return build_runner(
        name or settings.agent_runner,
        codex_binary=settings.codex_binary,
        codex_model=settings.codex_model,
        claude_binary=settings.claude_binary,
        claude_model=settings.claude_model,
        timeout_seconds=settings.agent_timeout_seconds,
    )


def _embedding_provider(settings: Settings):
    if not settings.research_embedding_base_url or not settings.research_embedding_model:
        return None
    return OpenAICompatibleEmbeddingProvider(
        base_url=settings.research_embedding_base_url,
        api_key=settings.research_embedding_api_key,
        model=settings.research_embedding_model,
        timeout_seconds=settings.research_embedding_timeout_seconds,
    )


def _deep_read_service(
    settings: Settings,
    source: ZoteroPaperSource,
    bridge: MKGBridge,
    *,
    runner_name: str | None = None,
) -> DeepReadService:
    return DeepReadService(
        settings,
        source,
        bridge,
        _runner(settings, runner_name),
        embedding_provider=_embedding_provider(settings),
    )


def _print_results(results: list[SyncResult]) -> None:
    table = Table(title="Sync results")
    table.add_column("itemKey")
    table.add_column("MKG identifier")
    table.add_column("status")
    table.add_column("concepts", justify="right")
    table.add_column("error")
    for result in results:
        table.add_row(
            result.item_key,
            result.identifier,
            result.status,
            str(result.concepts_count),
            result.error or "",
        )
    console.print(table)

    failed = sum(result.status == "failed" for result in results)
    processed = sum(result.processed for result in results)
    skipped = sum(result.skipped for result in results)
    console.print(
        f"total={len(results)} processed={processed} skipped={skipped} failed={failed}"
    )
    if failed:
        raise typer.Exit(code=1)


@app.command()
def doctor() -> None:
    """Verify MCP, semantic index, vendored skill, CLI agents and MKG DB."""
    settings = load_settings()
    required = {
        "get_item_details",
        "get_content",
        "get_collections",
        "get_collection_items",
        "search_library",
        "find_similar",
        "semantic_status",
    }

    try:
        skill = load_ljg_paper_skill()
        console.print(f"[green]ljg-paper vendored[/green]: revision={skill.revision}")

        for runner_name in ("codex", "claude"):
            runner = _runner(settings, runner_name)
            available = runner.available()
            version = getattr(runner, "version", lambda: None)()
            console.print(
                f"Agent {runner_name}: available={available}"
                + (f" version={version}" if version else "")
            )

        if settings.research_embedding_base_url and settings.research_embedding_model:
            console.print(
                "Research embedding: configured "
                f"model={settings.research_embedding_model} "
                f"base_url={settings.research_embedding_base_url}"
            )
        else:
            console.print("Research embedding: not configured (optional until Level-2 embedding)")

        with ZoteroMCPClient(settings.zotero_mcp_url) as client:
            client.ping()
            tools = client.list_tools()
            names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
            missing = sorted(required - names)
            source = ZoteroPaperSource(client, settings.zotero_library_id)
            semantic = source.semantic_status()

            console.print(f"[green]MCP reachable[/green]: {settings.zotero_mcp_url}")
            console.print(f"MCP tools: {len(names)}")
            if missing:
                console.print(f"[red]Missing tools:[/red] {', '.join(missing)}")
            else:
                console.print("[green]Required MCP tools available[/green]")

            ready = semantic.get("ready")
            message = semantic.get("message") or semantic
            console.print(f"Semantic index ready: {ready}")
            console.print(f"Semantic status: {message}")

            with MKGBridge(settings, source) as bridge:
                stats = bridge.stats()
                console.print(f"MKG DB: {settings.mkg_db_path}")
                console.print_json(json.dumps(stats, ensure_ascii=False))

            if missing or ready is False:
                raise typer.Exit(code=1)
    except (MCPError, OSError, ValueError, FileNotFoundError) as exc:
        console.print(f"[red]Doctor failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("collections")
def collections() -> None:
    """Print the Zotero collection tree returned by the running plugin."""
    with runtime() as (_, _, source, _):
        payload = source.get_collections()
        console.print_json(json.dumps(payload, ensure_ascii=False, default=str))


@app.command("sync-item")
def sync_item(
    item_key: str = typer.Argument(..., help="Zotero item key"),
    process: bool = typer.Option(False, "--process", help="Run MKG concept extraction"),
    force: bool = typer.Option(False, "--force", help="Reprocess even when content hash is unchanged"),
) -> None:
    with runtime() as (_, _, _, bridge):
        result = bridge.sync_item(item_key, process=process, force=force)
        _print_results([result])


@app.command("sync-collection")
def sync_collection(
    collection_key: str = typer.Argument(..., help="Zotero collection key"),
    process: bool = typer.Option(False, "--process", help="Run MKG concept extraction"),
    force: bool = typer.Option(False, "--force", help="Reprocess unchanged papers"),
    limit: int = typer.Option(500, min=1, max=5000),
) -> None:
    with runtime() as (_, _, source, bridge):
        keys = source.collection_item_keys(collection_key, limit=limit)
        console.print(f"Found {len(keys)} Zotero items")
        results = bridge.sync_items(keys, process=process, force=force)
        _print_results(results)


@app.command("sync-library")
def sync_library(
    process: bool = typer.Option(False, "--process", help="Run MKG concept extraction"),
    force: bool = typer.Option(False, "--force", help="Reprocess unchanged papers"),
    limit: int = typer.Option(500, min=1, max=5000),
    offset: int = typer.Option(0, min=0),
) -> None:
    with runtime() as (_, _, source, bridge):
        keys = source.library_item_keys(limit=limit, offset=offset)
        console.print(f"Found {len(keys)} Zotero items")
        results = bridge.sync_items(keys, process=process, force=force)
        _print_results(results)


@app.command("build-similarity")
def build_similarity(
    top_k: int = typer.Option(8, min=1, max=100),
    min_score: float = typer.Option(0.55, min=0.0, max=1.0),
) -> None:
    """Build paper similarity edges using Zotero's existing embedding index."""
    with runtime() as (_, _, _, bridge):
        result = bridge.build_similarity(top_k=top_k, min_score=min_score)
        console.print_json(json.dumps(result))


@app.command("deep-read")
def deep_read(
    item_key: str = typer.Argument(..., help="Zotero item key"),
    runner: str | None = typer.Option(None, "--runner", help="codex or claude"),
    force: bool = typer.Option(False, "--force", help="Repeat deep read even when unchanged"),
    embed: bool = typer.Option(True, "--embed/--no-embed", help="Embed signature when configured"),
) -> None:
    """Run Level-2 ljg-paper deep reading through Codex or Claude."""
    with runtime() as (settings, _, source, bridge):
        service = _deep_read_service(settings, source, bridge, runner_name=runner)
        result = service.deep_read(item_key, force=force, embed=embed)
        console.print_json(json.dumps(asdict(result), ensure_ascii=False))
        if result.status == "failed":
            raise typer.Exit(code=1)


@app.command("embed-research")
def embed_research(
    item_key: str = typer.Argument(..., help="Zotero item key with completed deep read"),
    force: bool = typer.Option(False, "--force", help="Re-embed unchanged signature"),
) -> None:
    """Embed the typed PaperSignature, not the paper full text."""
    with runtime() as (settings, _, source, bridge):
        if _embedding_provider(settings) is None:
            console.print("[red]Research embedding endpoint/model is not configured[/red]")
            raise typer.Exit(code=2)
        service = _deep_read_service(settings, source, bridge)
        changed = service.embed_item(item_key, force=force)
        console.print_json(json.dumps({"item_key": item_key, "embedded": changed}))


@app.command("build-research-similarity")
def build_research_similarity(
    model: str | None = typer.Option(None, "--model"),
    top_k: int = typer.Option(8, min=1, max=100),
    min_score: float = typer.Option(0.55, min=-1.0, max=1.0),
) -> None:
    """Build similarity edges in the PaperSignature embedding space."""
    with runtime() as (settings, _, source, bridge):
        service = _deep_read_service(settings, source, bridge)
        result = service.build_research_similarity(
            model=model,
            top_k=top_k,
            min_score=min_score,
        )
        console.print_json(json.dumps(result, ensure_ascii=False))


@app.command()
def stats() -> None:
    """Show bridge, deep-read and graph counts."""
    with runtime() as (_, _, _, bridge):
        console.print_json(json.dumps(bridge.stats(), ensure_ascii=False))


if __name__ == "__main__":
    app()
