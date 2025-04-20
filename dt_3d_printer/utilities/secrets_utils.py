import json


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
