#!/usr/bin/env python3
import os
import json
import uuid
import shutil
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger("spine2d-mcp.spine2d_integration")

class Spine2DIntegration:
    """Integration with SPINE2D for character rigging and animation export"""
    
    def __init__(self, storage_dir: str = "./storage"):
        self.storage_dir = storage_dir
        self.rigs_dir = os.path.join(storage_dir, "rigs")
        self.exports_dir = os.path.join(storage_dir, "exports")
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure storage directories exist"""
        os.makedirs(self.storage_dir, exist_ok=True)
        os.makedirs(self.rigs_dir, exist_ok=True)
        os.makedirs(self.exports_dir, exist_ok=True)
    
    def rig_character(self, character_id: str) -> Dict[str, Any]:
        """Create a SPINE2D rig for a character"""
        try:
            from psd_parser import PsdParser
            
            # Get character metadata
            parser = PsdParser(self.storage_dir)
            metadata = parser.get_character_metadata(character_id)
            
            if metadata is None:
                raise ValueError(f"Character not found: {character_id}")
            
            # Generate rig ID
            rig_id = f"rig_{str(uuid.uuid4())[:8]}_{character_id}"
            rig_dir = os.path.join(self.rigs_dir, rig_id)
            os.makedirs(rig_dir, exist_ok=True)
            
            # Analyze layers to determine character structure
            layers = metadata.get("layers", [])
            rig_data = self._analyze_character_structure(layers)
            
            # Create SPINE2D skeleton
            skeleton = self._create_skeleton(rig_data, metadata["dimensions"])
            
            # Create skin attachments
            skin = self._create_skin(rig_data, character_id, metadata)
            
            # Create IK constraints
            ik_constraints = self._create_ik_constraints(rig_data, skeleton)
            
            # Create SPINE2D project
            spine_project = {
                "skeleton": {
                    "hash": str(uuid.uuid4()),
                    "spine": "4.1.00",
                    "width": metadata["dimensions"]["width"],
                    "height": metadata["dimensions"]["height"],
                    "images": f"../characters/{character_id}/",
                    "audio": ""
                },
                "bones": skeleton["bones"],
                "slots": skeleton["slots"],
                "skins": {
                    "default": skin
                },
                "ik": ik_constraints,
                "animations": {}
            }
            
            # Save rig metadata
            rig_metadata = {
                "rig_id": rig_id,
                "character_id": character_id,
                "bone_count": len(skeleton["bones"]),
                "ik_count": len(ik_constraints),
                "created_at": self._get_timestamp()
            }

            self._save_rig_data(rig_dir, spine_project, rig_metadata)

            return {
                "rig_id": rig_id,
                "bone_count": len(skeleton["bones"]),
                "ik_count": len(ik_constraints)
            }
            
        except Exception as e:
            logger.error(f"Error rigging character {character_id}: {e}")
            raise
    
    def _analyze_character_structure(self, layers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze character layers to determine structure"""
        rig_data = {
            "bones": {},
            "layer_slots": [],
            "hierarchy": {}
        }

        # Expanded keyword matching for bone assignment
        bone_keywords = {
            "hair": ["hair", "bang", "ponytail"],
            "eyebrow": ["eyebrow", "brow"],
            "eye": ["eye", "iris", "irides", "eyewhite", "pupil", "eyelash"],
            "head": ["head", "face"],
            "neck": ["neck", "collar"],
            "headwear": ["headwear", "hat", "cap", "helmet"],
            "body": ["body", "torso", "chest", "shirt", "jacket", "clothes", "topwear"],
            "arm_left": ["arm_left", "left_arm", "leftarm", "sleeve_l", "handwear-l", "handwear_l"],
            "arm_right": ["arm_right", "right_arm", "rightarm", "sleeve_r", "handwear-r", "handwear_r"],
            "hand_left": ["hand_left", "left_hand", "lefthand"],
            "hand_right": ["hand_right", "right_hand", "righthand"],
            "leg_left": ["leg_left", "left_leg", "leftleg"],
            "leg_right": ["leg_right", "right_leg", "rightleg"],
            "foot_left": ["foot_left", "left_foot", "leftfoot"],
            "foot_right": ["foot_right", "right_foot", "rightfoot"],
            "bottomwear": ["bottomwear", "pants", "skirt", "shorts", "legwear"],
            "objects": ["objects", "weapon", "prop", "item"],
        }

        hierarchy = {
            "root": ["body", "bottomwear", "objects"],
            "body": ["head", "neck", "headwear", "arm_left", "arm_right", "leg_left", "leg_right"],
            "head": ["hair", "eyebrow", "eye"],
            "arm_left": ["hand_left"],
            "arm_right": ["hand_right"],
            "leg_left": ["foot_left"],
            "leg_right": ["foot_right"]
        }

        flat_layers = self._flatten_layers(layers)

        for layer in flat_layers:
            layer_name = layer["name"].lower().replace("-", " ").replace("_", " ")
            matched_bone = None

            for bone_name, keywords in bone_keywords.items():
                if any(kw in layer_name for kw in keywords):
                    matched_bone = bone_name
                    break

            if matched_bone is None:
                matched_bone = "body"

            # First matching layer provides bone position
            if matched_bone not in rig_data["bones"]:
                rig_data["bones"][matched_bone] = layer

            rig_data["layer_slots"].append({
                "layer": layer,
                "bone": matched_bone
            })

        rig_data["hierarchy"] = hierarchy
        return rig_data
    
    def _flatten_layers(self, layers: List[Dict[str, Any]], parent_path: str = "") -> List[Dict[str, Any]]:
        """Flatten nested layers structure"""
        result = []
        
        for layer in layers:
            # Add current layer
            if layer["type"] != "group":
                result.append(layer)
            
            # Process children if it's a group
            if "children" in layer and isinstance(layer["children"], list):
                result.extend(self._flatten_layers(layer["children"], layer["path"]))
        
        return result
    
    def _create_skeleton(self, rig_data: Dict[str, Any], dimensions: Dict[str, int]) -> Dict[str, Any]:
        """Create SPINE2D skeleton from rig data"""
        bones = []
        slots = []
        cx = dimensions["width"] / 2
        cy = dimensions["height"] / 2

        # Root bone at canvas center
        bones.append({"name": "root", "x": cx, "y": cy, "length": 50})

        # Create bones for matched body parts
        for bone_name, layer in rig_data["bones"].items():
            parent = "root"
            for parent_name, children in rig_data["hierarchy"].items():
                if bone_name in children:
                    parent = parent_name
                    break

            if "position" in layer and "dimensions" in layer:
                x = layer["position"]["x"] + layer["dimensions"]["width"] / 2 - cx
                y = cy - layer["position"]["y"] - layer["dimensions"]["height"] / 2
                length = max(layer["dimensions"]["width"], layer["dimensions"]["height"]) / 2
            else:
                x, y, length = 0, 0, 50

            bones.append({"name": bone_name, "parent": parent, "x": x, "y": y, "length": length})

        # Create slots for ALL layers in draw order
        bone_names = {b["name"] for b in bones}
        for slot_info in rig_data["layer_slots"]:
            layer = slot_info["layer"]
            bone = slot_info["bone"]
            if bone not in bone_names:
                bone = "root"

            if layer.get("image_path"):
                attachment_name = layer["image_path"].replace(".png", "")
                slots.append({
                    "name": f"slot_{layer['id']}",
                    "bone": bone,
                    "attachment": attachment_name
                })

        return {"bones": bones, "slots": slots}
    
    def _create_skin(self, rig_data: Dict[str, Any], character_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create skin attachments for ALL layers"""
        skin = {}

        for slot_info in rig_data["layer_slots"]:
            layer = slot_info["layer"]
            if layer.get("image_path"):
                slot_name = f"slot_{layer['id']}"
                attachment_name = layer["image_path"].replace(".png", "")
                w = layer.get("dimensions", {}).get("width", 100)
                h = layer.get("dimensions", {}).get("height", 100)

                skin[slot_name] = {
                    attachment_name: {
                        "x": 0,
                        "y": 0,
                        "width": w,
                        "height": h,
                        "path": layer["image_path"]
                    }
                }

        return skin
    
    def _create_ik_constraints(self, rig_data: Dict[str, Any], skeleton: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create IK constraints for the skeleton"""
        ik_constraints = []
        bones = rig_data.get("bones", {})

        if "arm_right" in bones and "hand_right" in bones:
            ik_constraints.append({
                "name": "arm_right_ik",
                "target": "hand_right",
                "bones": ["arm_right"],
                "mix": 1,
                "bendPositive": True
            })

        if "arm_left" in bones and "hand_left" in bones:
            ik_constraints.append({
                "name": "arm_left_ik",
                "target": "hand_left",
                "bones": ["arm_left"],
                "mix": 1,
                "bendPositive": False
            })

        if "leg_right" in bones and "foot_right" in bones:
            ik_constraints.append({
                "name": "leg_right_ik",
                "target": "foot_right",
                "bones": ["leg_right"],
                "mix": 1,
                "bendPositive": False
            })

        if "leg_left" in bones and "foot_left" in bones:
            ik_constraints.append({
                "name": "leg_left_ik",
                "target": "foot_left",
                "bones": ["leg_left"],
                "mix": 1,
                "bendPositive": False
            })

        return ik_constraints
    
    def _save_rig_data(self, rig_dir: str, spine_project: Dict[str, Any], metadata: Dict[str, Any]):
        """Save rig data to JSON file"""
        # Save metadata
        metadata_path = os.path.join(rig_dir, "metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Save SPINE2D project
        project_path = os.path.join(rig_dir, "spine_project.json")
        with open(project_path, "w") as f:
            json.dump(spine_project, f, indent=2)
    
    def export_animation(self, character_id: str, animation_id: str, format: str = "json") -> Dict[str, Any]:
        """Export animation to SPINE2D format"""
        try:
            from animation_generator import AnimationGenerator
            
            # Get animation data
            generator = AnimationGenerator(self.storage_dir)
            animation_data = generator.get_animation_data(animation_id)
            animation_metadata = generator.get_animation_metadata(animation_id)
            
            if animation_data is None or animation_metadata is None:
                raise ValueError(f"Animation not found: {animation_id}")
            
            # Get character rig
            rig_id = self._find_rig_for_character(character_id)
            
            if rig_id is None:
                raise ValueError(f"No rig found for character: {character_id}")
            
            # Load rig data
            rig_dir = os.path.join(self.rigs_dir, rig_id)
            project_path = os.path.join(rig_dir, "spine_project.json")
            
            with open(project_path, "r") as f:
                spine_project = json.load(f)
            
            # Convert animation data to SPINE2D format
            animation_name = animation_metadata.get("animation_type", "animation")
            spine_animation = self._convert_to_spine_animation(animation_data)
            
            # Add animation to SPINE2D project
            spine_project["animations"][animation_name] = spine_animation
            
            # Generate export ID
            export_id = f"export_{str(uuid.uuid4())[:8]}_{animation_id}"
            export_dir = os.path.join(self.exports_dir, export_id)
            os.makedirs(export_dir, exist_ok=True)
            
            # Save export metadata
            export_metadata = {
                "export_id": export_id,
                "character_id": character_id,
                "animation_id": animation_id,
                "format": format,
                "created_at": self._get_timestamp()
            }
            
            metadata_path = os.path.join(export_dir, "metadata.json")
            with open(metadata_path, "w") as f:
                json.dump(export_metadata, f, indent=2)
            
            # Copy character images into export directory
            char_images_src = os.path.join(self.storage_dir, "characters", character_id)
            char_images_dst = os.path.join(export_dir, "images")
            if os.path.isdir(char_images_src):
                if os.path.isdir(char_images_dst):
                    shutil.rmtree(char_images_dst)
                shutil.copytree(char_images_src, char_images_dst)
                # Update images path in spine project to be relative to the JSON file
                spine_project["skeleton"]["images"] = "images/"
                logger.info(f"Copied character images to {char_images_dst}")

            # Export in requested format
            export_path = ""

            if format == "json":
                export_path = os.path.join(export_dir, f"{animation_name}.json")
                with open(export_path, "w") as f:
                    json.dump(spine_project, f, indent=2)
            elif format == "png":
                # In a real implementation, we would render frames as PNG
                export_path = os.path.join(export_dir, f"{animation_name}.png")
                # Placeholder for rendering
                with open(export_path, "w") as f:
                    f.write("PNG output placeholder")
            elif format == "gif":
                # In a real implementation, we would render as GIF
                export_path = os.path.join(export_dir, f"{animation_name}.gif")
                # Placeholder for rendering
                with open(export_path, "w") as f:
                    f.write("GIF output placeholder")
            
            return {
                "export_id": export_id,
                "format": format,
                "file_path": export_path,
                "animation_name": animation_name
            }
            
        except Exception as e:
            logger.error(f"Error exporting animation {animation_id}: {e}")
            raise
    
    def _find_rig_for_character(self, character_id: str) -> Optional[str]:
        """Find a rig ID for a character"""
        if not os.path.isdir(self.rigs_dir):
            return None
        
        # Iterate through rig directories
        for rig_dir_name in os.listdir(self.rigs_dir):
            rig_path = os.path.join(self.rigs_dir, rig_dir_name)
            
            if os.path.isdir(rig_path):
                metadata_path = os.path.join(rig_path, "metadata.json")
                
                if os.path.isfile(metadata_path):
                    try:
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                            
                            if metadata.get("character_id") == character_id:
                                return rig_dir_name
                    except Exception as e:
                        logger.warning(f"Failed to read metadata for {rig_dir_name}: {e}")
        
        return None
    
    def _convert_to_spine_animation(self, animation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert our animation data to SPINE2D animation format"""
        spine_animation = {
            "bones": {},
            "slots": {},
            "deform": {},
            "drawOrder": [],
            "events": []
        }
        
        # Convert keyframes
        for bone_name, keyframes in animation_data.get("keyframes", {}).items():
            bone_animation = {}
            
            # Handle different properties
            for prop in ["rotate", "translate", "scale"]:
                bone_animation[prop] = []
            
            for keyframe in keyframes:
                time = keyframe.get("time", 0)
                
                # Handle rotation
                if "rotation" in keyframe:
                    bone_animation["rotate"].append({
                        "time": time,
                        "angle": keyframe["rotation"],
                        "curve": "stepped"
                    })
                
                # Handle translation
                if "x" in keyframe or "y" in keyframe:
                    bone_animation["translate"].append({
                        "time": time,
                        "x": keyframe.get("x", 0),
                        "y": keyframe.get("y", 0),
                        "curve": "stepped"
                    })
            
            # Only add bone if it has animations
            if bone_animation["rotate"] or bone_animation["translate"] or bone_animation["scale"]:
                spine_animation["bones"][bone_name] = bone_animation
        
        # Handle facial expressions as slot attachments
        if "face" in animation_data.get("keyframes", {}):
            slot_animation = {
                "attachment": []
            }
            
            for keyframe in animation_data["keyframes"]["face"]:
                if "expression" in keyframe:
                    slot_animation["attachment"].append({
                        "time": keyframe.get("time", 0),
                        "name": f"face_{keyframe['expression']}"
                    })
            
            spine_animation["slots"]["slot_face"] = slot_animation
        
        # Add particle effects if any
        if "particles" in animation_data:
            event_frames = []
            
            for particle in animation_data["particles"]:
                event_frames.append({
                    "time": 0,
                    "name": f"effect_{particle['type']}",
                    "string": particle.get("color", "#FFFFFF"),
                    "int": particle.get("count", 10),
                    "float": particle.get("duration", 1.0)
                })
            
            if event_frames:
                spine_animation["events"] = event_frames
        
        return spine_animation
    
    def get_rig_metadata(self, rig_id: str) -> Optional[Dict[str, Any]]:
        """Get rig metadata by ID"""
        rig_dir = os.path.join(self.rigs_dir, rig_id)
        metadata_path = os.path.join(rig_dir, "metadata.json")
        
        if not os.path.isfile(metadata_path):
            return None
        
        with open(metadata_path, "r") as f:
            return json.load(f)
    
    def get_export_metadata(self, export_id: str) -> Optional[Dict[str, Any]]:
        """Get export metadata by ID"""
        export_dir = os.path.join(self.exports_dir, export_id)
        metadata_path = os.path.join(export_dir, "metadata.json")
        
        if not os.path.isfile(metadata_path):
            return None
        
        with open(metadata_path, "r") as f:
            return json.load(f)
    
    def list_exports(self, character_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all exports, optionally filtered by character"""
        exports = []
        
        # Check if exports directory exists
        if not os.path.isdir(self.exports_dir):
            return exports
        
        # Iterate through export directories
        for export_dir_name in os.listdir(self.exports_dir):
            export_path = os.path.join(self.exports_dir, export_dir_name)
            
            if os.path.isdir(export_path):
                metadata_path = os.path.join(export_path, "metadata.json")
                
                if os.path.isfile(metadata_path):
                    try:
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                            
                            # Filter by character_id if provided
                            if character_id is None or metadata.get("character_id") == character_id:
                                exports.append({
                                    "id": metadata.get("export_id"),
                                    "character_id": metadata.get("character_id"),
                                    "animation_id": metadata.get("animation_id"),
                                    "format": metadata.get("format"),
                                    "created_at": metadata.get("created_at")
                                })
                    except Exception as e:
                        logger.warning(f"Failed to read metadata for {export_dir_name}: {e}")
        
        return exports
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        return datetime.utcnow().isoformat() + "Z"