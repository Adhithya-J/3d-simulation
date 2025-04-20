import subprocess
import json
from stl import mesh
from pathlib import Path
import os
from typing import Union, Optional
from dt_3d_printer.utilities import secrets_utils


SECRETS_PATH = Path("secrets.json")
DEFAULT_TIMEOUT = 300
REQUIRED_CONFIG_FIELDS = ["version", "inherits", "overrides"]

def validate_environment(cura_engine_path: Path) -> bool:
    """
    Validate that CuraEngine is available and working.
    
    Args:
        cura_engine_path: Path to the CuraEngine executable
        
    Returns:
        True if validation passes
        
    Raises:
        RuntimeError: If CuraEngine is not found or fails to run
    """

    try:
        result = subprocess.run(
            [str(cura_engine_path),"help"],
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
        raise RuntimeError(f"CuraEngine not found at {cura_engine_path}")
        

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"CuraEngine version check failed: {e.stderr}")
        


def validate_config(config_path : Path) -> bool:
    """
    Validate that the config file exists and has the required structure.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        True if validation passes
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid
    """

    # config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        missing_fields = [field for field in REQUIRED_CONFIG_FIELDS if field not in config]
        if missing_fields:
            print(f"Config file missing recommended fields: {', '.join(missing_fields)}")
        
        #for field in REQUIRED_CONFIG_FIELDS:
        #    if field not in config:
        #        pass
                # raise ValueError(f"Config file missing required {field}")
        return True  
    

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Config file validation failed: {str(e)}")
      

def validate_stl(stl_path : Path) -> bool:
    """
    Validate that the STL file exists and can be read.
    
    Args:
        stl_path: Path to the STL file
        
    Returns:
        True if validation passes
        
    Raises:
        RuntimeError: If STL file is invalid
    """
    # stl_path = Path(stl_path)

    try: 
        stl_mesh = mesh.Mesh.from_file(stl_path)
        print(f"STL is valid and contains {len(stl_mesh.vectors)} triangles")
        return True
    except Exception as e:
        raise RuntimeError(f"STL Error: {e}")

def check_file_access(file_path : Path) -> bool:
    """
    Check if a file can be accessed, using platform-appropriate methods.
    
    Args:
        file_path: Path to check
        
    Returns:
        True if file is accessible
    """
    if not file_path.exists():
        return False
    try:
        with open(file_path, 'r') as f:
            f.read(1)  # Try to read one byte
        return True
    except Exception:
        return False


def slice_with_curaengine(
        stl_path : Union[str, Path], 
        output_dir: Union[str, Path], 
        config_path: Union[str,Path]="fdmprinter.def.json",
        timeout: int= DEFAULT_TIMEOUT) -> Path:

    """
    Slice an STL file using CuraEngine.
    
    Args:
        stl_path: Path to the STL file
        output_dir: Directory to save the output GCode
        config_path: Path to the CuraEngine config file
        timeout: Maximum time to wait for CuraEngine (seconds)
        
    Returns:
        Path to the generated GCode file
        
    Raises:
        FileNotFoundError: If required files don't exist
        RuntimeError: If slicing fails
        TimeoutError: If CuraEngine takes too long
    """

    stl_path = Path(stl_path).resolve()
    output_dir = Path(output_dir).resolve()
    config_path = Path(config_path).resolve()

    if not stl_path.exists():
        raise FileNotFoundError(f"STL file not found: {stl_path}")
    else:
        print(f"STL exists: {stl_path}")
    
    try:
        cura_engine_path = Path(secrets_utils.get_value_from_json(
            SECRETS_PATH,"slicing","cura_engine_path")).resolve() 
    except Exception as e:
        raise RuntimeError(f"Failed to get CuraEngine from secrets: {e}")
    
    validate_environment(cura_engine_path)
    validate_stl(stl_path)
    validate_config(config_path)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not os.access(output_dir, os.W_OK):
        raise PermissionError(f"No write permission for output directory: {output_dir}")

    print(f"Output directory is writable: {output_dir}")

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
                                timeout=timeout)

        print("CuraEngine completed with return code: %d", result.returncode)
        
        stdout_lines = result.stdout.split("\n")
        if stdout_lines:
            for line in stdout_lines[-5:]:
                if line.strip():
                    print(line)

        if result.stderr.strip():
            print("Stderr output")
            for line in result.stderr.split("\n"):
                if line.strip():
                    print(line)

        """
        print("\n=== ENGINE OUTPUT ===")
        print("Return code:", result.returncode)
        print("Stdout (last 10 lines):")
        print('\n'.join(result.stdout.split('\n')[-10:]))
        print("Stderr (full):")
        print(result.stderr)
        """

        if result.returncode !=0:
            error_msg = f"""
            CuraEngine Failed with code: {result.returncode}
            Command: {' '.join(cmd)}
            --- STDOUT ---
            {result.stdout}
            --- STDERR ---
            {result.stderr}
            """
            raise RuntimeError(error_msg)

        if not gcode_path.exists():
            raise RuntimeError(f"CuraEngine ran successfully but no output file was created at {gcode_path}")

        return gcode_path
    
    except subprocess.TimeoutExpired:
        raise TimeoutError("CuraEngine timed out after {timeout} seconds")

    except subprocess.CalledProcessError as e:
        print(f"\n[FATAL ERROR] {str(e)}")
        if hasattr(e, "stdout") and e.stdout:
            print("Last stdout: %s", e.stdout.split("\n")[-5:])
        if hasattr(e, "stderr") and e.stderr:
            print("Stderr: %s", e.stderr)

        # 'stdout' in locals():
        #print("Last output lines:", result.stdout.split('\n')[-5:])
        raise RuntimeError(f"Slicing failed: {e.stderr}")

def main() -> None:
    """Main entry point for the STL processor."""

    try:   
        stl_file = Path(secrets_utils.get_value_from_json(SECRETS_PATH,"slicing","stl_file"))
        output_dir = Path(secrets_utils.get_value_from_json(SECRETS_PATH,"slicing","output_dir"))
        config_file = Path(secrets_utils.get_value_from_json(SECRETS_PATH,"slicing","config_file"))
        

        if not check_file_access(config_file):
            raise RuntimeError(f"File might be locked or inaccessible: {config_file}")

        gcode_path = slice_with_curaengine(stl_file, output_dir, config_file)
        print(f"CuraEngine Generated Gcode: {gcode_path}")
    
    except Exception as e:
        raise RuntimeError(f"Error: {e}")



if __name__ == "__main__":
    main()