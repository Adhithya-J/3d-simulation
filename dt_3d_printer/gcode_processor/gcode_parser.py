import re
from pathlib import Path
from dt_3d_printer.utilities import secrets_utils

SECRETS_PATH = Path("secrets.json")

class GCodeParser:

    def __init__(self):
        self.current_position = {"X": 0, "Y": 0, "Z" : 0, "E": 0, "F":0}
        self.absolute_positioning = True
        self.absolute_extrusion = True
        self.current_layer = 0
        # self.layer_data = {}
        self.parsed_data = {
            "metadata":{},
            "layers":{}
        }

    def parse_gcode(self, gcode):

        lines = gcode.split("\n")

        for line in lines:

            line = line.strip()
            if not line:
                continue
            if line.startswith(";"):
                self._parse_comment(line)
                continue

            line = line.split(";")[0].strip()

            self._process_command(line)

    def _parse_comment(self, comment_line):

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

    def _process_command(self, command):

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
        
    def _parse_params(self,command):
        
        matches = re.findall(f"([XYZEFS])([-+]?[0-9]*\.?[0-9]+)",command)
        return {axis: float(value) for axis, value in matches}

    def _process_movement(self,command):

        params = self._parse_params(command)


        if "F" in params:
            self.current_position["F"] = params["F"]
        
        new_position = self.current_position.copy()
        for axis in ["X","Y","Z", "E"]:
            if axis in params:
                if self.absolute_positioning or axis=="E" or self.absolute_extrusion:
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
    
    
    def _process_set_position(self,command):
        
        params = self._parse_params(command)

        for axis, value in params.items():
            if axis in self.current_position:
                self.current_position[axis] = float(value)

    def get_absolute_coordinates(self):
        return self.parsed_data
    


if __name__ == "__main__":


    file_path = secrets_utils.get_value_from_json(SECRETS_PATH,"parser","gcode_file")

    with open(file_path) as f:
        gcode = f.read()

    parser = GCodeParser()
    parser.parse_gcode(gcode)
    coordinates = parser.get_absolute_coordinates()
    
    # Print the extracted coordinates for each layer
    for layer, points in coordinates['layers'].items():
        print(f"\nLayer {layer}:")
        for point in points:
            print(f"X:{point['X']:.3f} Y:{point['Y']:.3f} Z:{point['Z']:.3f} E:{point['E']:.3f} F:{point['F']}")