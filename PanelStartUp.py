import adsk.core, adsk.fusion, math, re, subprocess, os, time, webbrowser, traceback

def run(context):
    # Set global variables
    global app, ui, product, design, rootComp

    app = adsk.core.Application.get()
    ui = app.userInterface
    product = app.activeProduct
    design = adsk.fusion.Design.cast(product)
    rootComp = design.rootComponent

    # Prompt the user to select the front face.
    global selection
    selection = ui.selectEntity('Select a face to be the new front view.', 'Faces')

    # list of functions 
    rotateBodiesToFont()    # Rotates the bodies around the Z axis so the front of the panel is the front view
    moveBodiesToOrgin()     # Moves all bodies to the origin
    stockBody()             # Create a stock body for Charles setup
    changeUnits()           # Change units to inches
    identifyFoam()          # Identify and rename foam bodies
    identifyBump()          # Identify and rename bump bodies
    identifyStuds()         # Identify and rename stud bodies
    identifyTrack()         # Identify and rename track bodies
    openBIM()               # Opens BIM in the browser
    isReturn()              # Is there a return on the right side of the panel that would interfer with WCS?
    melvinOrgin()           # Creates a sketch and contruction point for the Melvin WCS
    charlesOrgin()          # Creates a sketch and contruction point for the Charles WCS
    mergeSheathin()         # Merge all sheathing panels into one
    camWorkspace()          # Create the cam workspace
    melvinSetup()           # Need to create Melvin orgin point before this will work
    charlesSetup()          # Create the Charles setup
    foamErrorDetection()    # Compare Foam and Sheathing X, Y, and Z dimensions to find errors from Revit export.

def rotateBodiesToFont():
    # Check if a selection was made. If the user cancels, the selection object is None.
    if not selection:
        ui.messageBox('No face was selected. The script will now exit.')
        return

    # Get the selected face directly from the selection object.
    selected_face = selection.entity
    
    # Ensure the selected entity is a BRepFace.
    if not isinstance(selected_face, adsk.fusion.BRepFace):
        ui.messageBox('Please select a valid BRepFace.')
        return

    # Get the normal vector of the selected face in the global coordinate system.
    face_evaluator = selected_face.evaluator
    
    # Use the centroid of the face as a point to get the normal.
    point_on_face = selected_face.centroid
    
    success, face_normal = face_evaluator.getNormalAtPoint(point_on_face)
    
    if not success:
        ui.messageBox('Could not get the normal vector for the selected face. The script will now exit.')
        return
        
    face_normal.normalize()

    # This script only works for faces with normals parallel to the XY plane.
    if abs(face_normal.z) > 1e-6:
        ui.messageBox('This script only supports faces with normals parallel to the XY plane. Please select a different face.')
        return
    
    # Define the target vector for the new front view (negative Y-axis).
    target_front_vector = adsk.core.Vector3D.create(0, -1, 0)

    # Use the atan2 function to get the signed angle from the X-axis to the face normal.
    angle_rad_face = math.atan2(face_normal.y, face_normal.x)
    
    # The angle of the target negative Y-axis is -pi/2.
    angle_rad_target = -math.pi / 2
    
    # The required rotation is the difference between the target and face angles.
    angle_to_rotate = angle_rad_target - angle_rad_face

    # Get the bounding box of the entire design's root component.
    bounding_box = rootComp.boundingBox
    # Calculate the center of the bounding box to use as the rotation origin.
    center_x = (bounding_box.minPoint.x + bounding_box.maxPoint.x) / 2.0
    center_y = (bounding_box.minPoint.y + bounding_box.maxPoint.y) / 2.0
    center_z = (bounding_box.minPoint.z + bounding_box.maxPoint.z) / 2.0
    rotation_origin = adsk.core.Point3D.create(center_x, center_y, center_z)

    # Create the transformation matrix with the calculated angle, Z-axis, and rotation origin.
    final_transform = adsk.core.Matrix3D.create()
    z_axis = adsk.core.Vector3D.create(0, 0, 1)
    final_transform.setToRotation(angle_to_rotate, z_axis, rotation_origin)

    # Get the MoveFeatures collection from the root component.
    moveFeatures = rootComp.features.moveFeatures

    # Create an ObjectCollection to hold ALL bodies to be moved.
    bodiesToMove = adsk.core.ObjectCollection.create()
    for body in rootComp.bRepBodies:
        bodiesToMove.add(body)
        

    if bodiesToMove.count > 0:
        # Create a move input with all bodies and the final transformation matrix.
        moveInput = moveFeatures.createInput(bodiesToMove, final_transform)

        # Add the move feature to the design.
        moveFeatures.add(moveInput)
    else:
        ui.messageBox('No bodies found in the root component to move.')
        return

    # Set the active camera to the new front view to refresh the viewport.
    # The new "front" view is now aligned with the negative Y-axis.
    camera = app.activeViewport.camera
    camera.viewOrientation = adsk.core.ViewOrientations.FrontViewOrientation
    app.activeViewport.camera = camera
    app.activeViewport.fit() # Fit the view to the new position of the assembly

def moveBodiesToOrgin():
    # Find 'Body1' and rename as "Exterior"
    body1 = None
    for body in rootComp.bRepBodies:
        if body.name == 'Body1':
            body1 = body
            break       
         
    # Rename the selected body
    body1.name = "Exterior"

    # Create a vector representing panel coordinate system
    panelCoord = adsk.core.Vector3D.create(body1.boundingBox.maxPoint.x, body1.boundingBox.maxPoint.y, body1.boundingBox.maxPoint.z)

    # Create a vector representing the translation needed to move to the origin (0,0,0)
    translationVector = adsk.core.Vector3D.create(-panelCoord.x, -panelCoord.y, -panelCoord.z)

    # Create a transformation matrix from the translation vector
    transformMatrix = adsk.core.Matrix3D.create()
    transformMatrix.translation = translationVector

    # Get the move features collection
    moveFeatures = rootComp.features.moveFeatures

    # Create an ObjectCollection to hold ALL bodies to be moved
    bodiesToMove = adsk.core.ObjectCollection.create()
    for body in rootComp.bRepBodies:
        bodiesToMove.add(body)

    # Create a move input with all bodies and the transformation matrix
    moveInput = moveFeatures.createInput(bodiesToMove, transformMatrix)

    # Add the move feature to the design
    moveFeatures.add(moveInput)

    # Fit the view to the new position of the assembly
    app.activeViewport.fit()

def stockBody():
    # Find Exterior Body 
    target_body_name = "Exterior"
    body_to_copy = None
    for body in rootComp.bRepBodies:
        if body.name == target_body_name:
            body_to_copy = body
            break

    # Copy the body
    copy_paste_features = rootComp.features.copyPasteBodies
    bodies_to_copy_collection = adsk.core.ObjectCollection.create()
    bodies_to_copy_collection.add(body_to_copy)
    new_bodies_collection = copy_paste_features.add(bodies_to_copy_collection).bodies # Get the 'bodies' collection directly

    new_body = new_bodies_collection.item(0) # Get the first (and likely only) copied body

    # Move the new copy -.4 in the Y-axis (will be machine +Z axis)
    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(0, -0.4, 0)

    move_features = rootComp.features.moveFeatures
    bodies_to_move = adsk.core.ObjectCollection.create()
    bodies_to_move.add(new_body)

    move_feature_input = move_features.createInput(bodies_to_move, transform)
    move_features.add(move_feature_input)

    # Rename the new copy to "Stock"
    new_body.name = "Stock"
    #new_body.appearance = design.appearances.itemByName('Paint - Enamel Glossy (Green)')

    # Hide the stock body
    adsk.fusion.Design.cast(app.activeProduct).rootComponent.bRepBodies.itemByName('Stock').isVisible = False

def changeUnits():
    # Get the UnitManager from the active design
    unitMgr = design.unitsManager

    # Get the current default length units as a string
    current_units_str = unitMgr.defaultLengthUnits.lower()

    # Define the commands to change units to inches
    txtCmds = [
        u"NaFusionUI.ChangeActiveUnitsCmd ",
        u"Commands.SetString infoUnitsType InchImperial",
        u"NuCommands.CommitCmd",
    ]
    if current_units_str != 'in':
        [app.executeTextCommand(cmd) for cmd in txtCmds]

def identifyFoam():
    foam_dim_in = 3.0
    foam_dim_cm = foam_dim_in * 2.54
    tolerance_cm = .001 * 2.54      
    foam_bodies = [] 
    
    # Iterate through all bodies in the root component.
    for body in rootComp.bRepBodies:
        boundingBox = body.boundingBox
        width = boundingBox.maxPoint.y - boundingBox.minPoint.y
        
        if (abs(width - foam_dim_cm) < tolerance_cm):
            # Add the body to the list and rename it
            foam_bodies.append(body)
            body.name = "Foam"

def identifyBump():
    bump_track_dim_in = 6.086
    bump_track_dim_cm = bump_track_dim_in * 2.54
    tolerance_cm = .001 * 2.54    
    bump_track_bodies = [] 
    
    # Iterate through all bodies in the root component.
    for body in rootComp.bRepBodies:
        boundingBox = body.boundingBox

        length = boundingBox.maxPoint.x - boundingBox.minPoint.x
        width = boundingBox.maxPoint.y - boundingBox.minPoint.y
        height = boundingBox.maxPoint.z - boundingBox.minPoint.z
        
        if (abs(length - bump_track_dim_cm) < tolerance_cm) :
            # Add the body to the list and rename it
            bump_track_bodies.append(body)
            body.name = "Bump"

    # Bump stud 6" X 2.5"
    bump_stud_w_dim_in = 6.0
    bump_stud_h_dim_in = 2.5
    bump_stud_w_dim_cm = bump_stud_w_dim_in * 2.54
    bump_stud_h_dim_cm = bump_stud_h_dim_in * 2.54

    bump_stud_bodies = [] 

    for body in rootComp.bRepBodies:
        boundingBox = body.boundingBox

        length = boundingBox.maxPoint.x - boundingBox.minPoint.x
        width = boundingBox.maxPoint.y - boundingBox.minPoint.y
        
        if (abs(length - bump_stud_w_dim_cm) < tolerance_cm and
            abs(width - bump_stud_h_dim_cm) < tolerance_cm):
            # Add the body to the list and rename it
            bump_stud_bodies.append(body)
            body.name = "Bump"

def identifyStuds():
    stud_dim_in = 6.0
    stud_dim_cm = stud_dim_in * 2.54
    tolerance_cm = .001 * 2.54   
    stud_bodies = [] 
    
    # Iterate through all bodies in the root component.
    for body in rootComp.bRepBodies:
        boundingBox = body.boundingBox
        width = boundingBox.maxPoint.y - boundingBox.minPoint.y
        
        if (abs(width - stud_dim_cm) < tolerance_cm):
            # Add the body to the list and rename it
            stud_bodies.append(body)
            body.name = "Stud"
            
def identifyTrack():
    track_dim_in = 6.143
    track_dim_cm = track_dim_in * 2.54
    tolerance_cm = .001 * 2.54    
    track_bodies = [] 
    
    # Iterate through all bodies in the root component.
    for body in rootComp.bRepBodies:
        boundingBox = body.boundingBox
        width = boundingBox.maxPoint.y - boundingBox.minPoint.y
        
        if (abs(width - track_dim_cm) < tolerance_cm) :
            # Add the body to the list and rename it
            track_bodies.append(body)
            body.name = "Track"

def openBIM():
    script_path = r"C:\Users\ahughes\Documents\Python BIM\pyBIM.pyw"
    if os.path.exists(script_path):
        current_doc_name = app.activeDocument.name
        panel_number = re.sub(r'\s*[vV]\d+', '', current_doc_name) 
        system_python = r"C:/Users/ahughes/AppData/Local/Programs/Python/Python313/pythonw.exe"
        subprocess.Popen([system_python, os.path.realpath(script_path), panel_number])
        time.sleep(1)
    else:
        webbrowser.open_new_tab("https://bim360field.autodesk.com/equipment") 

def isReturn():
    studs = [body for body in rootComp.bRepBodies if body.name.startswith("Stud")]
    if not studs:
        # Ask User if the panel has a window
        question_text = "Does this panel have return on the side of the coordinate system (right side)?"
        button_type = adsk.core.MessageBoxButtonTypes.YesNoButtonType
        global returnResult 
        returnResult = ui.messageBox(question_text, "Script Question", button_type)
        return None, None

    # The code below tried to identify if there is a return on either side of the Panel.
    # Initialize min and max values
    min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
    max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')

    # Loop through all "Stud" bodies and expand bounds
    for body in studs:
        box = body.boundingBox
        min_x = min(min_x, box.minPoint.x)
        min_y = min(min_y, box.minPoint.y)
        min_z = min(min_z, box.minPoint.z)
        max_x = max(max_x, box.maxPoint.x)
        max_y = max(max_y, box.maxPoint.y)
        max_z = max(max_z, box.maxPoint.z)

    # Create Point3D objects for easy use later
    global stud_max_point
    stud_min_point = adsk.core.Point3D.create(min_x, min_y, min_z)
    stud_max_point = adsk.core.Point3D.create(max_x, max_y, max_z)
        
    if (stud_min_point.x / 2.54) < -4:
        returnResult = adsk.core.DialogResults.DialogYes
    
    exteriorBox_min_x, exteriorBox_min_y, exteriorBox_min_z= float('-inf'), float('-inf'), float('-inf')

    for body in rootComp.bRepBodies:
        if body.name == 'Exterior':
            exteriorBox = body.boundingBox
            exteriorBox_min_x = min(exteriorBox_min_x, exteriorBox.minPoint.x)
            exteriorBox_min_y = min(exteriorBox_min_y, exteriorBox.minPoint.y)
            exteriorBox_min_z = min(exteriorBox_min_z, exteriorBox.minPoint.z)
    
    exterior_min_point = adsk.core.Point3D.create(exteriorBox_min_x, exteriorBox_min_y, exteriorBox_min_z)

    global westReturn
    westReturn = False
    if ((exterior_min_point.x / 2.54) + stud_min_point.x) < -4:
        westReturn = True

def melvinOrgin():
    body = rootComp.bRepBodies.item(0)
    
    # Compute overall bounding box extents
    min_x, max_x = float('inf'), float('-inf')
    min_y, max_y = float('inf'), float('-inf')
    min_z, max_z = float('inf'), float('-inf')

    for face in body.faces:
        boundingBox = face.boundingBox
        min_x = min(min_x, boundingBox.minPoint.x)
        max_x = max(max_x, boundingBox.maxPoint.x)
        min_y = min(min_y, boundingBox.minPoint.y)
        max_y = max(max_y, boundingBox.maxPoint.y)
        min_z = min(min_z, boundingBox.minPoint.z)
        max_z = max(max_z, boundingBox.maxPoint.z)
    
    # Back-top-right corner
    corner_x, corner_y, corner_z = max_x, max_y, max_z

    # Same X/Z offset as before, but +6" (15.24 cm) added to Y
    offset_x = corner_x - (0.0625 * 2.54)
    offset_y = corner_y - (6.0 * 2.54)
    offset_z = corner_z - (0.0625 * 2.54)

    # Optional alternate X offset if dialog says “Yes”
    if returnResult == adsk.core.DialogResults.DialogYes:
        if any("Stud" in body.name for body in rootComp.bRepBodies):
            offset_x = corner_x - (abs(stud_max_point.x))
        else:
            offset_x = corner_x - (4.6875 * 2.54)

    construction_point = adsk.core.Point3D.create(offset_x, offset_y, offset_z)

    # Create the point in the design
    sketches = rootComp.sketches
    sketch = sketches.add(rootComp.xYConstructionPlane)
    sketchPoint = sketch.sketchPoints.add(construction_point)
    constructionPoints = rootComp.constructionPoints
    point_input = constructionPoints.createInput()
    point_input.setByPoint(sketchPoint)
    new_point = constructionPoints.add(point_input)
    new_point.name = 'Point1'

    app.activeViewport.fit()

def charlesOrgin():
    body = rootComp.bRepBodies.item(0)
    
    min_x, max_x, min_y, max_y, min_z, max_z = float('inf'), float('-inf'), float('inf'), float('-inf'), float('inf'), float('-inf')

    for face in body.faces:
        boundingBox = face.boundingBox
        min_x = min(min_x, boundingBox.minPoint.x); max_x = max(max_x, boundingBox.maxPoint.x)
        min_y = min(min_y, boundingBox.minPoint.y); max_y = max(max_y, boundingBox.maxPoint.y)
        min_z = min(min_z, boundingBox.minPoint.z); max_z = max(max_z, boundingBox.maxPoint.z)
    
    # Max extents define the "Back Top Right" corner
    corner_x, corner_y, corner_z = max_x, max_y, max_z
    
    # Calculate the offset point (0.0625 inward for X and Z, no offset for Y)
    offset_x = corner_x - (0.0625 * 2.54) 
    offset_y = corner_y
    offset_z = corner_z - (0.0625 * 2.54) 

    if returnResult == adsk.core.DialogResults.DialogYes:
        if any("Stud" in body.name for body in rootComp.bRepBodies):
            offset_x = corner_x - (abs(stud_max_point.x))
        else:
            offset_x = corner_x - (4.6875 * 2.54)

    construction_point = adsk.core.Point3D.create(offset_x, offset_y, offset_z)

    # Create a sketch and add a sketch point
    sketches = rootComp.sketches
    sketch = sketches.add(rootComp.xYConstructionPlane)  # temporary reference plane
    sketchPoint = sketch.sketchPoints.add(construction_point)
    constructionPoints = rootComp.constructionPoints
    point_input = rootComp.constructionPoints.createInput()
    point_input.setByPoint(sketchPoint)
    new_point = constructionPoints.add(point_input)
    new_point.name = 'Point2'
    app.activeViewport.fit()

def mergeSheathin():
    # This script merges all bodies with dimension that equals 0.625

    sheathing_thickness = 0.625 * 2.54
    tolerance_cm = 0.01 * 2.54
    
    bodies_to_merge = []
    
    # Iterate through all bodies in the root component.
    for body in rootComp.bRepBodies:
        boundingBox = body.boundingBox
        width = boundingBox.maxPoint.y - boundingBox.minPoint.y

        if (abs(width - sheathing_thickness) < tolerance_cm):
            
            bodies_to_merge.append(body)

    # Iterate through all occurrences (sub-components) of the root component.
    for comp_occurrence in rootComp.allOccurrences:
        component = comp_occurrence.component
        for body in component.bRepBodies:
            boundingBox = body.boundingBox
            width = boundingBox.maxPoint.y - boundingBox.minPoint.y
            
            if (abs(width - sheathing_thickness) < tolerance_cm):
                
                bodies_to_merge.append(body)

    if len(bodies_to_merge) > 1:
        combineFeatures = rootComp.features.combineFeatures
        targetBody = bodies_to_merge[0]
        
        for i in range(1, len(bodies_to_merge)):
            toolBody = bodies_to_merge[i]
            
            toolBodies_collection = adsk.core.ObjectCollection.create()
            toolBodies_collection.add(toolBody)
            
            combineInput = combineFeatures.createInput(targetBody, toolBodies_collection)
            combineInput.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
            
            combineFeature = combineFeatures.add(combineInput)
            targetBody = combineFeature.bodies.item(0)
        
        if targetBody:
            targetBody.name = "Sheathing"
        
    else:
        ui.messageBox('No bodies found with a bounding box dimension of 0.625 inches.', 'Info')

def camWorkspace():
    # Define global variables to be used with both Mevlin and Charles setups
    global cam, setups, doc, cam_product,camOcc, setupInput

    # Switch to Manufacture Workspace
    ui.workspaces.itemById('CAMEnvironment').activate()

    # Get the active product.
    cam = adsk.cam.CAM.cast(app.activeProduct)

    # Get the Setups collection.
    
    setups = cam.setups

    # Create a SetupsInput object to define a milling setup.
    setupInput = setups.createInput(adsk.cam.OperationTypes.MillingOperation)

    # Get the CAM product from the document's products collection
    doc = app.activeDocument
    cam_product = doc.products.itemByProductType('CAMProductType')
    cam = adsk.cam.CAM.cast(cam_product)

    # Specify the first body in the model as the model geometry.
    camOcc = cam.designRootOccurrence
    setupInput.models = [camOcc.bRepBodies[0]]

def melvinSetup():
    # Create the setup.
    setup = setups.add(setupInput)

    # Set the name of the setup to "Melvin"
    setup.name = "Melvin"

    # Set the program name to file name + "M" for Melvin
    progNameParam = setup.parameters.itemByName('job_programName')
    stringVal: adsk.cam.StringParameterValue = progNameParam.value
    current_doc_name = app.activeDocument.name
    cleaned_name = re.sub(r'\s*[vV]\d+', '', current_doc_name) 
    stringVal.value = (cleaned_name + "M")
    
    # Find and assign the machine from the Local Library
    machine_model_to_find = "Melvin"
    found_machine = None

    # Get the CAMManager and LibraryManager
    camManager = adsk.cam.CAMManager.get()
    libraryManager = camManager.libraryManager

    # Get the singular MachineLibrary object
    machineLibrary = libraryManager.machineLibrary

    # Get the URL for the Local machine library location
    local_machine_url = machineLibrary.urlByLocation(adsk.cam.LibraryLocations.LocalLibraryLocation)
    #local_machine_url = machineLibrary.urlByLocation(adsk.cam.LibraryLocations.CloudLibraryLocation)

    # Get the machines from this specific local library URL
    local_machines = list(machineLibrary.childMachines(local_machine_url))

    # Loop through the found machines to find yours by model name
    for machine_item in local_machines:
        if machine_item.model == machine_model_to_find:
            found_machine = machine_item
            break
            
    setup.machine = found_machine

    # Select Stock for Melvin setup
    design_product = doc.products.itemByProductType('DesignProductType')
    rootComp1 = design_product.rootComponent # This is the correct root component
    stock_body = rootComp1.bRepBodies.itemByName('Sheathing')

    # Change stock mode
    prmStockMode = setup.parameters.itemByName('job_stockMode')
    prmStockMode.expression = "'solid'"

    stock_solids_collection = adsk.core.ObjectCollection.create()
    stock_solids_collection.add(stock_body)
    setup.stockSolids = stock_solids_collection 

    # Select origin for Melvin setup
    sketchPoint = rootComp.constructionPoints.itemByName('Point1')
    setup.parameters.itemByName('wcs_origin_mode').expression = "'point'"
    setup.parameters.itemByName('wcs_origin_point').value.value = [sketchPoint]
    setup.parameters.itemByName('wcs_orientation_flipX').value.value = True
    setup.parameters.itemByName('wcs_orientation_flipZ').value.value = True

    # Get the model's Y construction axis
    z_axis_entity = rootComp.yConstructionAxis 
    # Assign a Python list containing the axis entity directly
    setup.parameters.itemByName('wcs_orientation_axisZ').value.value = [z_axis_entity]
    
    # Load templates from cloud for Melvin
    template_names_to_load = [
            "Melvin 2 Pass NEW"
        ]

    camManager = adsk.cam.CAMManager.get()
    libraryManager = camManager.libraryManager
    templateLibrary = libraryManager.templateLibrary

    cloud_template_url = templateLibrary.urlByLocation(adsk.cam.LibraryLocations.CloudLibraryLocation)

    cloud_templates = list(templateLibrary.childTemplates(cloud_template_url))

    for template_name in template_names_to_load:
        found_template = [item for item in cloud_templates if item.name == template_name][0] # Assumes template is found
        setup.createFromCAMTemplate(found_template)

    # Set entry point for Perimeter ToolPath
    melvin_setup = None
    for setup_index in range(cam.setups.count):
        current_setup = cam.setups.item(setup_index)
        if current_setup.name == "Melvin":
            melvin_setup = current_setup
            break

    perimeter_op = None
    for op_index in range(melvin_setup.operations.count):
        op = melvin_setup.operations.item(op_index)
        if op.name == "Perimeter":
            perimeter_op = op
            break 

    perimeter_op.parameters.itemByName('entryPositions').value.value = [sketchPoint]

def charlesSetup():
    # Look for body that is 3" thick 
    global foamresult
    foamresult = False
    
    # Checks for total thickness of panel. Could get false positive for panels with bumps but not foam.
    for body in rootComp.bRepBodies:
        boundingBox = body.boundingBox
        width = boundingBox.maxPoint.y - boundingBox.minPoint.y
        if width > (6.9 * 2.54):
            foamresult = True

    # Checks for body named "Foam"        
    if any("Foam" in body.name for body in rootComp.bRepBodies):
        foamresult = True

    #if foamresult == True:
    if foamresult == True:
        # Create a SetupsInput object to define a milling setup.
        setupInput = setups.createInput(adsk.cam.OperationTypes.MillingOperation)

        # Get the CAM product from the document's products collection
        doc = app.activeDocument
        cam_product = doc.products.itemByProductType('CAMProductType')
        cam = adsk.cam.CAM.cast(cam_product)

        # Specify the first body in the model as the model geometry.
        camOcc = cam.designRootOccurrence
        setupInput.models = [camOcc.bRepBodies[0]]

        # Set the origin to be at the top center of the model box.
        originParam = setupInput.parameters.itemByName('wcs_origin_mode')
        choiceVal: adsk.cam.ChoiceParameterValue = originParam.value
        choiceVal.value = 'modelPoint'

        originPoint = setupInput.parameters.itemByName('wcs_origin_boxPoint')
        choiceVal: adsk.cam.ChoiceParameterValue = originPoint.value
        choiceVal.value = 'top center'

        # Set the comment for the program.
        #commentParam = setupInput.parameters.itemByName('job_programComment')
        #commentParam.value.value = 'This is the comment.'

        # Create the setup.
        setup = setups.add(setupInput)

        # Set the name of the setup to "Melvin"
        setup.name = "Charles"

        # Set the program name to file name + "M" for Melvin
        progNameParam = setup.parameters.itemByName('job_programName')
        stringVal: adsk.cam.StringParameterValue = progNameParam.value
        current_doc_name = app.activeDocument.name
        cleaned_name = re.sub(r'\s*[vV]\d+', '', current_doc_name) 
        stringVal.value = (cleaned_name + "C")

        # Find and assign the machine from the Local Library
        machine_model_to_find = "Charles"
        found_machine = None

        # Get the CAMManager and LibraryManager
        camManager = adsk.cam.CAMManager.get()
        libraryManager = camManager.libraryManager

        # Get the singular MachineLibrary object
        machineLibrary = libraryManager.machineLibrary

        # Get the URL for the Local machine library location
        local_machine_url = machineLibrary.urlByLocation(adsk.cam.LibraryLocations.CloudLibraryLocation)

        # Get the machines from this specific local library URL
        local_machines = list(machineLibrary.childMachines(local_machine_url))

        # Loop through the found machines to find yours by model name
        for machine_item in local_machines:
            if machine_item.model == machine_model_to_find:
                found_machine = machine_item
                break
                
        setup.machine = found_machine

        # Select Stock for Charles setup
        stock_body = rootComp.bRepBodies.itemByName('Stock')

        # Change stock mode
        prmStockMode = setup.parameters.itemByName('job_stockMode')
        prmStockMode.expression = "'solid'"

        stock_solids_collection = adsk.core.ObjectCollection.create()
        stock_solids_collection.add(stock_body)
        setup.stockSolids = stock_solids_collection 

        # Set Origin
        sketchPoint = rootComp.constructionPoints.itemByName('Point2')
        setup.parameters.itemByName('wcs_origin_mode').expression = "'point'"
        setup.parameters.itemByName('wcs_origin_point').value.value = [sketchPoint]
        setup.parameters.itemByName('wcs_orientation_flipX').value.value = True
        setup.parameters.itemByName('wcs_orientation_flipZ').value.value = True

        # Get the model's Y construction axis
        z_axis_entity = rootComp.yConstructionAxis 
        # Assign a Python list containing the axis entity directly
        setup.parameters.itemByName('wcs_orientation_axisZ').value.value = [z_axis_entity]
        
        template_names_to_load = []
        # Load templates from cloud for Charles
        if not any(body.name == "Bump" for body in rootComp.bRepBodies):
            template_names_to_load.append("Charles Facinghead")
        
        template_names_to_load.extend([
                "Charles Perimeter",
                "Charles Perimeter Above Sheathing",
                "Charles Brick Feature FM"
        ])

        if any("Bump" in body.name for body in rootComp.bRepBodies):
            template_names_to_load.append("Charles Bump Clean Up FM")
     
        if returnResult == adsk.core.DialogResults.DialogYes:
            # Load templates from cloud for Charles
            template_names_to_load.extend([
                    "Charles Return EM",
                    "Charles Return FM"
                ])
            
        # if westReturn == True:
        #     template_names_to_load.extend([
        #             "Charles Return EM",
        #             "Charles Return FM"
        #         ])


        camManager = adsk.cam.CAMManager.get()
        libraryManager = camManager.libraryManager
        templateLibrary = libraryManager.templateLibrary

        cloud_template_url = templateLibrary.urlByLocation(adsk.cam.LibraryLocations.CloudLibraryLocation)

        cloud_templates = list(templateLibrary.childTemplates(cloud_template_url))

        for template_name in template_names_to_load:
            found_template = [item for item in cloud_templates if item.name == template_name][0] 
            setup.createFromCAMTemplate(found_template)

def foamErrorDetection():  
    # Iterate through all bodies within the current component
    for body in rootComp.bRepBodies:
        # Check if the body's name is "sheathing" (case-sensitive)
        if body.name == "Sheathing" or body.name.lower() == "foam":
            body.isVisible = True

    if foamresult == True:
        # Get the "Foam" and "Sheathing" bodies
        foamBody = None
        sheathingBody = None
        
        #for body in camOcc.bRepBodies:
        for body in rootComp.bRepBodies:
            if body.name == "Foam":
                foamBody = body
            elif body.name == "Sheathing":
                sheathingBody = body

        if not foamBody:
            ui.messageBox('Could not find a body named "Foam".', 'Body Not Found')
            return
        if not sheathingBody:
            ui.messageBox('Could not find a body named "Sheathing".', 'Body Not Found')
            return

        # Get the bounding boxes for each body
        foamBounds = foamBody.boundingBox
        sheathingBounds = sheathingBody.boundingBox

        # Calculate dimensions for Foam
        foamLength = foamBounds.maxPoint.x - foamBounds.minPoint.x
        foamHeight = foamBounds.maxPoint.z - foamBounds.minPoint.z

        # Calculate dimensions for Sheathing
        sheathingLength = sheathingBounds.maxPoint.x - sheathingBounds.minPoint.x
        sheathingHeight = sheathingBounds.maxPoint.z - sheathingBounds.minPoint.z
        
        # Define the tolerance
        tolerance = 1.0 * 2.54 

        # Calculate differences and convert to inches
        diffLength = abs((foamLength - sheathingLength) / 2.54)
        diffHeight = abs((foamHeight - sheathingHeight) / 2.54)

        if diffLength > 0.003 or diffHeight > 0.003:
            # Prepare the message for differences less than 1 inch
            alert_messages = []
            if diffLength < tolerance:
                alert_messages.append(f"X difference: {diffLength:.3f} inches")
            if diffHeight < tolerance and diffHeight > 0.003:
                alert_messages.append(f"Z difference: {diffHeight:.3f} inches")

            if alert_messages:
                message = "The dimension difference between 'Foam' and 'Sheathing' is less than 1 inch in the following directions:\n"
                message += "\n".join(alert_messages)
                ui.messageBox(message, 'Dimension Alert')
            else:
                message = "The dimension difference between 'Foam' and 'Sheathing' is 1 inch or more in all directions.\n"
                message += f"X difference: {diffLength:.3f} inches\n"
                message += f"Z difference: {diffHeight:.3f} inches"
                ui.messageBox(message, 'Dimension Alert')
