from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager

import typer
from rich.console import Console
from rich.table import Table

from .config import Settings, load_settings
from .mcp_client import MCPError, ZoteroMCPClient
from .mkg_bridge import MKGBridge, SyncResult
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
    """Verify MCP connectivity, required tools, semantic index and MKG DB access."""
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
    except (MCPError, OSError, ValueError) as exc:
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


@app.command()
def stats() -> None:
    """Show bridge and MKG graph counts."""
    with runtime() as (_, _, _, bridge):
        console.print_json(json.dumps(bridge.stats(), ensure_ascii=False))


if __name__ == "__main__":
    app()
