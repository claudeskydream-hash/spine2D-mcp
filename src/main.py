#!/usr/bin/env python3
import os
import sys
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("spine2d-mcp")


def main():
    parser = argparse.ArgumentParser(description='SPINE2D Animation MCP Server')
    parser.add_argument('--storage', default='./storage', help='Storage directory path')
    args = parser.parse_args()

    os.makedirs(args.storage, exist_ok=True)

    from server import mcp
    import server
    from psd_parser import PsdParser
    from animation_generator import AnimationGenerator
    from spine2d_integration import Spine2DIntegration

    server.psd_parser = PsdParser(args.storage)
    server.animation_generator = AnimationGenerator(args.storage)
    server.spine2d_integration = Spine2DIntegration(args.storage)

    logger.info("Starting SPINE2D Animation MCP Server")
    mcp.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
