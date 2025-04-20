import re
from pathlib import Path
from typing import Dict, List, Union, Optional
from dt_3d_printer.utilities import secrets_utils


SECRETS_PATH = Path("secrets.json")

class GCodeParser:
    """Parse GCode files and extract movement data organized by layers."""

    def __init__(self):
        """Initialize the GCode parser with default values."""
        self.current_position = {"X": 0.0, "Y": 0.0, "Z" : 0.0, "E": 0.0, "F":0.0}
        self.absolute_positioning = True
        self.absolute_extrusion = True
        self.current_layer = 0
        # self.layer_data = {}
        self.parsed_data = {
            "metadata":{},
            "layers":{}
        }

    def parse_gcode(self, gcode : str) -> None:
        """
        Parse GCode content and populate the parsed_data structure.
        
        Args:
            gcode: String containing GCode commands
        """
        if not gcode:
            raise ValueError("Empty GCode input")

        lines = gcode.split("\n")

        for line_num, line in enumerate(lines,1):
            try: 
                line = line.strip()
                if not line:
                    continue

                if line.startswith(";"):
                    self._parse_comment(line)
                    continue

                line = line.split(";")[0].strip()
                if line:
                    self._process_command(line)

            except Exception as e:
                raise RuntimeError(f"Error in parsing line {line_num}: {line}\n Error: {str(e)}")

    def _parse_comment(self, comment_line : str) -> None:
        """
        Extract metadata from comment lines.
        
        Args:
            comment_line: A GCode comment line (starting with ;)
        """

        if comment_line.startswith(";LAYER:"):
            try:
                self.current_layer = int(comment_line.split(":")[1])
            except ValueError:
                self.current_layer = 0
            
            if self.current_layer not in self.parsed_data['layers']:
                self.parsed_data['layers'][self.current_layer] = []
        
        elif ":" in comment_line:
            key_val = comment_line.lstrip(";").split(":",1)
            if len(key_val) == 2:
                key, value = key_val
                self.parsed_data["metadata"][key.strip()] = value.strip()

    def _process_command(self, command : str) -> None:
        """
        Process a GCode command and update internal state.
        
        Args:
            command: A GCode command without comments
        """
        
        if command == "G90":
            self.absolute_positioning = True    
        elif command == "G91":
            self.absolute_positioning = False
        elif command == "M82":
            self.absolute_extrusion = True
        elif command == "M83":
            self.absolute_extrusion = False

        elif command == "G28":
            self.current_position.update({"X": 0, "Y": 0, "Z" : 0})

        elif command.startswith("G0") or command.startswith("G1"):
            self._process_movement(command)
        
        elif command.startswith("G92"):
            self._process_set_position(command)
        
    def _parse_params(self,command : str) -> Dict[str, str]:
        """
        Extract parameters from a GCode command.
        
        Args:
            command: GCode command to parse
            
        Returns:
            Dictionary of axis letters to values
        """
        matches = re.findall(f"([XYZEFS])([-+]?[0-9]*\.?[0-9]+)",command)
        return {axis: float(value) for axis, value in matches}

    def _process_movement(self,command:str) -> None:
        """
        Process a movement command (G0/G1) and update position.
        
        Args:
            command: A GCode movement command
        """

        params = self._parse_params(command)

        if "F" in params:
            self.current_position["F"] = params["F"]
        
        new_position = self.current_position.copy()
        for axis in ["X","Y","Z", "E"]:
            if axis in params:
                if (self.absolute_positioning or 
                    (axis=="E" and self.absolute_extrusion)):
                    new_position[axis] = params[axis]
                else:
                    new_position[axis] += params[axis]
        if (new_position["X"]!= self.current_position["X"] or
            new_position["Y"]!= self.current_position["Y"] or
            new_position["Z"]!= self.current_position["Z"] or
            new_position["E"]!= self.current_position["E"]):

            point = {
                "X": new_position["X"],
                "Y": new_position["Y"],
                "Z": new_position["Z"],
                "E": new_position["E"],
                "F": new_position["F"]
            }

            if self.current_layer not in self.parsed_data["layers"]:
                self.parsed_data["layers"][self.current_layer] = []
            
            self.parsed_data["layers"][self.current_layer].append(point)

        self.current_position = new_position
    
    
    def _process_set_position(self,command:str) -> None:
        """
        Process a position setting command (G92).
        
        Args:
            command: G92 command with position values
        """
        params = self._parse_params(command)

        for axis, value in params.items():
            if axis in self.current_position:
                self.current_position[axis] = float(value)

    def get_absolute_coordinates(self) -> Dict:
        """
        Get the parsed GCode data.
        
        Returns:
            Dictionary containing metadata and layer-organized coordinate data
        """
        return self.parsed_data
    

def main():
    """Process a GCode file specified in secrets.json."""

    try:
        file_path = secrets_utils.get_value_from_json(SECRETS_PATH,"parser","gcode_file")

        with open(file_path) as f:
            gcode = f.read()

        parser = GCodeParser()
        parser.parse_gcode(gcode)
        coordinates = parser.get_absolute_coordinates()
        
        print(f"Found {len(coordinates['layers'])} layers")
        print(f"Metadata: {coordinates['metadata']}")
        

        # Print the extracted coordinates for each layer
        for layer, points in coordinates['layers'].items():
            print(f"\nLayer {layer}:")
            
            for i,point in enumerate(points[:3]):
                print(f"    {i+1}. X:{point['X']:.3f} Y:{point['Y']:.3f} Z:{point['Z']:.3f} E:{point['E']:.3f} F:{point['F']}")
            if len(points)>3:
                print(f" ... and {len(points)-3} more points")
    
    except Exception as e:
        raise RuntimeError(f"Error in processing GCode: {str(e)}")

if __name__ == "__main__":
    
    main()