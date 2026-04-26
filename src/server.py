#!/usr/bin/env python3
import os
import json
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from mcp.server.fastmcp import FastMCP

_executor = ThreadPoolExecutor(max_workers=4)

logger = logging.getLogger("spine2d-mcp")

mcp = FastMCP("spine2d-animation-server")

# Dependencies (set by main.py)
psd_parser = None
animation_generator = None
spine2d_integration = None


@mcp.tool()
def import_psd(file_path: str) -> str:
    """Upload and process a PSD file"""
    if not os.path.isfile(file_path):
        return json.dumps({"status": "error", "message": f"File not found: {file_path}"})

    if psd_parser is None:
        return json.dumps({"status": "error", "message": "PSD parser not initialized"})

    try:
        result = psd_parser.parse_psd(file_path)
        return json.dumps({
            "status": "success",
            "message": f"PSD file '{file_path}' imported successfully",
            "character_id": result["character_id"],
            "layers_count": result["layers_count"],
            "dimensions": result["dimensions"]
        }, indent=2)
    except Exception as e:
        logger.error(f"Error importing PSD: {e}")
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def setup_character(character_id: str) -> str:
    """Automatically rig the character"""
    if not character_id:
        return json.dumps({"status": "error", "message": "Missing character_id"})

    try:
        if psd_parser is None or spine2d_integration is None:
            return json.dumps({"status": "error", "message": "Server not initialized"})

        metadata = psd_parser.get_character_metadata(character_id)
        if metadata is None:
            return json.dumps({"status": "error", "message": f"Character not found: {character_id}"})

        result = spine2d_integration.rig_character(character_id)
        return json.dumps({
            "status": "success",
            "message": f"Character '{character_id}' rigged successfully",
            "rig_id": result["rig_id"],
            "bones_count": result["bone_count"],
            "ik_constraints": result["ik_count"]
        }, indent=2)
    except Exception as e:
        logger.error(f"Error setting up character: {e}")
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def generate_animation(character_id: str, description: str) -> str:
    """Create animation from text description"""
    if not character_id or not description:
        return json.dumps({"status": "error", "message": "Missing character_id or description"})

    try:
        if psd_parser is None or animation_generator is None:
            return json.dumps({"status": "error", "message": "Server not initialized"})

        metadata = psd_parser.get_character_metadata(character_id)
        if metadata is None:
            return json.dumps({"status": "error", "message": f"Character not found: {character_id}"})

        result = animation_generator.generate_animation(character_id, description)
        return json.dumps({
            "status": "success",
            "message": f"Animation '{description}' generated successfully",
            "animation_id": result["animation_id"],
            "animation_type": result["animation_type"],
            "emotion": result["emotion"],
            "duration": result["duration"]
        }, indent=2)
    except Exception as e:
        logger.error(f"Error generating animation: {e}")
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def preview_animation(character_id: str, animation_id: str) -> str:
    """Get a preview of the animation"""
    if not character_id or not animation_id:
        return json.dumps({"status": "error", "message": "Missing character_id or animation_id"})

    try:
        if spine2d_integration is None or animation_generator is None:
            return json.dumps({"status": "error", "message": "Server not initialized"})

        animation = animation_generator.get_animation_metadata(animation_id)
        if animation is None:
            return json.dumps({"status": "error", "message": f"Animation not found: {animation_id}"})

        result = spine2d_integration.export_animation(character_id, animation_id, "gif")
        return json.dumps({
            "status": "success",
            "message": f"Preview for animation '{animation_id}' generated",
            "preview_url": f"file://{result['file_path']}",
            "export_id": result["export_id"]
        }, indent=2)
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def export_animation(character_id: str, animation_id: str, format: str = "json") -> str:
    """Export the final animation"""
    if not character_id or not animation_id:
        return json.dumps({"status": "error", "message": "Missing character_id or animation_id"})

    try:
        if spine2d_integration is None or animation_generator is None:
            return json.dumps({"status": "error", "message": "Server not initialized"})

        animation = animation_generator.get_animation_metadata(animation_id)
        if animation is None:
            return json.dumps({"status": "error", "message": f"Animation not found: {animation_id}"})

        result = spine2d_integration.export_animation(character_id, animation_id, format)
        return json.dumps({
            "status": "success",
            "message": f"Animation '{animation_id}' exported as {format}",
            "export_url": f"file://{result['file_path']}",
            "export_id": result["export_id"],
            "animation_name": result["animation_name"]
        }, indent=2)
    except Exception as e:
        logger.error(f"Error exporting animation: {e}")
        return json.dumps({"status": "error", "message": str(e)})


@mcp.resource("spine2d://characters")
def get_characters() -> str:
    """List of available characters that have been imported"""
    try:
        if psd_parser is None:
            return json.dumps([])
        return json.dumps(psd_parser.list_characters(), indent=2)
    except Exception as e:
        logger.error(f"Error listing characters: {e}")
        return json.dumps([])
