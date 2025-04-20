import subprocess
import json
from stl import mesh
from pathlib import Path
import os


SECRETS_PATH = Path("secrets.json")

def get_value_from_json(json_file, key, sub_key):

    try:
        with open(json_file,"r") as f:
            data = json.load(f)
            return data[key][sub_key]
    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found error: {str(e.args)}")
    except KeyError as e:
        raise KeyError(f"Missing Key: {key} or Sub Key : {sub_key}")
    except Exception as e:
        raise RuntimeError(f"Error in reading json file: {str(e)}")


def validate_environment(cura_engine_path):

    try:
        result = subprocess.run(
            [ str(cura_engine_path),"help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        version_lines = [line for line in result.stdout.split("\n") if "Cura_SteamEngine" in line]
        
        if not version_lines:
            raise RuntimeError("CuraEngine output did not contain version info.")
        
        version_line = version_lines[0]
        print("CuraEngine found:", version_line.strip())
        return True

    except FileNotFoundError:
        raise RuntimeError(f"CuraEngine not found in Path.")
        

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"CuraEngine version check failed: {e.stderr.decode()}")
        


def validate_config(config_path):

    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        required_fields = ["version", "inherits", "overrides"]
        for field in required_fields:
            if field not in config:
                pass
                # raise ValueError(f"Config file missing required {field}")
        return True  
    

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Config file failed: {str(e)}")
      

def validate_stl(stl_path):
    stl_path = Path(stl_path)

    try: 
        new_mesh = mesh.Mesh.from_file(stl_path)
        print("STL is valid")
    except Exception as e:
        raise RuntimeError(f"STL Error: {e}")


def prepare_path(path):
    path = Path(path).absolute()
    path_str = path.as_posix()  

    return path_str


def slice_with_curaengine(stl_path, output_dir, config_path="fdmprinter.def.json"):

    stl_path = Path(stl_path).resolve()
    output_dir = Path(output_dir).resolve()
    config_path = Path(config_path).resolve()

    if not stl_path.exists():
        raise FileNotFoundError(f"STL file not found: {stl_path}")
    else:
        print(f"STL exists: {stl_path}")
    
    cura_engine_path = Path(get_value_from_json(SECRETS_PATH,"slicing","cura_engine_path")).resolve() 

    validate_environment(cura_engine_path)
    validate_stl(stl_path)
    validate_config(config_path)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    #os.chmod(output_dir, 0o755)
    print(f"Write test: {os.access(output_dir, os.W_OK)}")


    gcode_path = output_dir / f"{stl_path.stem}.gcode"
    

    cmd = [
         str(cura_engine_path),
        "slice",
        "-v",
        "-j", str(config_path),
        "-o", str(gcode_path),
        "-l", str(stl_path)

    ]

    try:
        result = subprocess.run(cmd, 
                                check=False,
                                stdout = subprocess.PIPE,
                                stderr = subprocess.PIPE,
                                stdin = subprocess.PIPE,
                                #capture_output=True, 
                                text=True,
                                encoding='utf-8',
                                errors = 'replace',
                                timeout=300)
        

        print("\n=== ENGINE OUTPUT ===")
        print("Return code:", result.returncode)
        print("Stdout (last 10 lines):")
        print('\n'.join(result.stdout.split('\n')[-10:]))
        print("Stderr (full):")
        print(result.stderr)
        
        if result.returncode !=0:
            error_msg = f"""
            CuraEngine Failed (Code: {result.returncode})
            Command: {' '.join(cmd)}
            --- STDOUT ---
            {result.stdout}
            --- STDERR ---
            {result.stderr}
            """
            raise RuntimeError(error_msg)

        return gcode_path
    
    except subprocess.TimeoutExpired:
        raise TimeoutError("CuraEngine timed out")

    except subprocess.CalledProcessError as e:
        print(f"\n[FATAL ERROR] {str(e)}")
        if 'stdout' in locals():
            print("Last output lines:", result.stdout.split('\n')[-5:])
        raise RuntimeError(f"Slicing failed: {e.stderr}")


def validate_gcode(gcode_path):
    raise NotImplementedError


def parse_code_robust(gcode_path):
    raise NotImplementedError



if __name__ == "__main__":
    try:
        
       
        stl_file = Path(get_value_from_json(SECRETS_PATH,"slicing","stl_file"))#.resolve() #r"D:\20 BTP\20mm_cube.stl"
        output_dir = Path(get_value_from_json(SECRETS_PATH,"slicing","output_dir"))#.resolve() #r"D:\20 BTP\cura_output"
        config_file = Path(get_value_from_json(SECRETS_PATH,"slicing","config_file"))#.resolve()  # r"D:\20 BTP\fdmprinter.def.json" # r"D:\20 BTP\fdmprinter.def.json" #r"C:\Program Files\UltiMaker Cura 5.9.0\share\cura\resources\definitions\fdmprinter.def.json"  #r"D:\20 BTP\minimal_config.def.json" # r"D:\20 BTP\fdmprinter.def.json" #
        # config_file = prepare_path(config_file)
        
        try:
            import win32file
            hfile = win32file.CreateFile(
                str(config_file),
                win32file.GENERIC_READ,
                0, None,
                win32file.OPEN_EXISTING,
                0, None
            )
            win32file.CloseHandle(hfile)
            print("File is not locked")
        except Exception as e:
            raise RuntimeError(f"File may be locked: {e}")

        gcode_path = slice_with_curaengine(stl_file, output_dir, config_file)
        print(f"CuraEngine Generated Gcode: {gcode_path}")
    
    except Exception as e:
        raise RuntimeError(f"Error: {e}")
