import omni
import asyncio
from pxr import Usd, UsdGeom, Gf, UsdShade, Sdf
import numpy as np

class MaterialFactory:
    """Material class to create material"""

    def __init__(self, stage, material_path):
        """Initialize the MaterialFactory"""
        # stage: USD to create the materials in
        # material_path: The USD path 
        self.stage = stage
        self.material_path = material_path
        self.material_prim = None

    def _create_material_prim(self):
        """Creates the base Material and Shader prims."""
        self.material_prim = UsdShade.Material.Define(self.stage, self.material_path)
        self.shader_prim = UsdShade.Shader.Define(self.stage, self.material_path + "/PBRShader")
        self.shader_prim.CreateAttr("UsdPreviewSurface")
    
    def set_pbr_properties(self, diffuse_color: Gf.Vec3f, roughness: float) -> UsdShade.Material:

        if not self.shader_prim:
            self._create_material_prim()
        self.shader_prim.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(diffuse_color)
        self.shader_prim.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
        output = self.material_prim.CreateSufraceOutput("surface")
        output.SetSource(self.shader_prim.ConnectableAPI(), "surface")
        print(f"Material '{self.material_path}' created with PBR properties")
        return self.material_prim
    
class CubePrinter:

    def __init__(self, stage: Usd.Stage, world_path : str = "/World", cube_name: str="PrintingCube",
                 layer_height_cm : float = 0.1, cube_dimension_cm : float = 10.0, num_contours : int=5):
        self.stage = stage
        self.world_path = world_path
        self.cube_name = cube_name
        self.cube_path = f"{world_path}/{cube_name}"
        self.layer_height_cm = layer_height_cm
        self.cube_dimension_cm = cube_dimension_cm
        self.num_layers = int(cube_dimension_cm/ layer_height_cm)
        self.num_contours = num_contours
        self.cube_prim = None
        self.pla_material_prim = None
        self.nozzle_path_material_prim = None

    def setup_materials(self):

        material_factory = MaterialFactory(self.stage, "/World/Materials/PLAMaterial")
        self.pla_material_prim = material_factory.set_pbr_properties(diffuse_color=Gf.Color3f(0.8,0.8,0.8), roughness = 0.5)

        nozzle_material = material_factory(self.stage, "/World/Materials/NozzlePathMaterial")
        self.nozzle_path_material_prim = nozzle_material.set_pbr_properties(diffuse_color = Gf.Color3f(1.0,0.0,0.9), roughness = 0.2)

    def create_cube_prim(self):
        self.cube_prim = UsdGeom.Cube.Define(self.stage, self.cube_path)
        self.cube_prim.CreateSizeAttr(self.cube_dimension_cm)
        self.cube_prim.CreateEntentAttr([(-self.cube_dimension_cm/2, -self.cube_dimension_cm/2, 0), (self.cube_dimension_cm/2, self.cube_dimension_cm/2, 0)])

        cube_xform_op = self.cube_prim.AddXformOp(UsdGeom.XformOP.TypeScale, UsdGeom.XformOp.PrecisionFloat, "transform")
        cube_xform_op.Set(Gf.Scale((1,1, 0.001)))

        material_binding_api = UsdShade.MaterialBindingAPI.ApplyAPI(self.cube_prim.GetPrim())
        material_binding_api.Bind(self.pla_material_prim)
        print(f"Cube prim '{self.cube_path}' created and material bound")

    def generate_layer_path(self, layer_number: int)->list:
        path_points = []
        step_in = (self.cube_dimension_cm / 2) / (self.num_contours+1)

        for i in range(self.num_contours, 0, -1):
            current_size = self.cube_dimension_cm - 2*step_in * (self.num_contours - i)
            half_size = current_size / 2.0
            z_pos = self.layer_height_cm * layer_number

            points = [
                (half_size, half_size, z_pos),
                (half_size, -half_size, z_pos),
                (-half_size, -half_size, z_pos),
                (-half_size, half_size, z_pos),
                (half_size, half_size, z_pos)
            ]

            path_points.extend([(float(x), float(y), float(z)) for x,y,z in points])

        return path_points
    

    async def print_layer(self, layer_num :int):

        print(f"Printing Layer: {layer_num+1}")

        current_z_scale = (layer_num +1) * self.layer_height_cm
        xform_op = self.cube_prim.GetXformOp()
        xform_op.Set(Gf.Scale((1,1, current_z_scale /(self.cube_dimension_cm / 2.0) ) ))

        layer_path = self.generate_layer_path(layer_num)

        line_prims = []
        for i in range(len(layer_path) -1):
            start_point = layer_path[i]
            end_point = layer_path[i+1]
            line_path_name = f"{self.cube_path}/Layer{layer_num+1}/NozzlePathLine{i}"
            line_prim = UsdGeom.Line.Define(self.stage, line_path_name)
            line_prim.CreatePointsAttr([Gf.Vec3f(*start_point), Gf.Vec3f(*end_point)])


            line_material_binding_api = UsdShade.MaterialBindingAPI.ApplyAPI(line_prim.GetPrim())
            line_material_binding_api.Bind(self.nozzle_path_material_prim)
            line_prims.append(line_prim)

        for line_prim in line_prims:
            await asyncio.sleep(0.05)


    async def run_simulation(self):

        print("Starting 3D printing simulation")
        self.setup_materials()
        self.create_cube_prim()

        for layer_num in range(self.num_layers):
            await self.print_layer(layer_num)
            await asyncio.sleep(0.2)
        
        print("3D printing simulation complete!")


async def setup_stage():

    stage : Usd.Stage = Usd.Stage.CreateNew()

    if not stage:
        return None

    omni.usd.get_context().set_stage(stage)

    meters_per_unit = 0.01
    Usd.UnitConversionSchema.SetStageMetersPerUnit(stage, meters_per_unit)
    Usd.UnitConversionSchema.SetStageUnitTag(stage, UsdGeom.Units.Centimeters)
    print(f"Stage units set to centimeters. Meters per unit: {meters_per_unit}")

    world_prim = UsdGeom.Xform.Define(stage,"/World")
    stage.SetDefaultPrim(world_prim.GetPrim())
    return stage


async def main():

    stage = await setup_stage()
    if not stage:
        omni.ui.NotificationWindow("Failed to setup USD stage. Check console for errors.", duration = 5.0, visible=True)
        return
    
    printer = CubePrinter(stage)
    await printer.run_simulation()

asyncio.ensure_future(main())