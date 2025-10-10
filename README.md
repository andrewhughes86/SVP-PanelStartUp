# Autodesk Fusion CAM Automation Script

This Python script for Autodesk Fusion automates the essential steps for preparing panel models for CNC machining on two custom linuxCNC machines, "Melvin" and "Charles." It handles model cleanup, orientation, material identification, work coordinate system (WCS) placement, and the creation of initial CAM setups.

***

## Key Features

* **Model Standardization:** Rotates the model based on user selection to align the desired **Front face** with the viewport, and moves all bodies to the **global origin (0, 0, 0)**.
* **Unit Enforcement:** Changes the active design units to **Inches**.
* **Component Identification:** Automatically identifies and renames core panel components based on thickness:
    * `Exterior` (Initial Body)
    * `Foam` (3.0" thick)
    * `Stud` (6.0" thick)
    * `Track` (6.143" thick)
    * `Sheathing` (0.625" thick, merged into one body)
* **Stock Creation:** Creates and offsets a copy of the `Exterior` body named **`Stock`** for the Charles setup.
* **"Bump" Handling:** Detects large structural "bumps" and performs **geometric cuts** on the `Stock` and `Foam` bodies to prevent collisions with the facing toolpath.
* **WCS Placement:** Creates machine-specific origin points (`Point1` for **Melvin**, `Point2` for **Charles**), automatically adjusting the X-offset if a panel **"return"** is detected or manually confirmed.
* **CAM Setup:** Switches to the **Manufacture Workspace** and creates initial CAM setups for both **Melvin** and **Charles**.
* **Process Checks:** Includes logic to check for **thin foam** and adjusts corresponding toolpath depths, and runs a **foam error detection** against sheathing dimensions.
* **External BIM Link:** Attempts to launch a local Python BIM tool or web page based on the panel's file name.
* **Status Reporting:** Gathers all warnings and status updates into a final message box for the user.

***

## Usage

1.  **Open the Panel Model:** Ensure your raw imported model is open and active in the **Design Workspace**.
2.  **Run the Script:** Access **Scripts and Add-Ins** in Fusion 360 and run the script.
3.  **Select Front Face:** The script's first prompt will ask you to select the face that should become the **Front View** (facing the camera along the negative Y-axis).
4.  **Answer Prompts:** The script may present a warning asking about a **right-side return** if frame detection fails; answer appropriately to ensure correct WCS placement.
5.  **Review Report:** A final message box will summarize any detected features or errors (e.g., "A bump has been detected.").
6.  **Select Toolpath Geometery:** The script concludes in the **Manufacture Workspace**, with the basic setups created and ready for toolpath generation.

***

## Notes and Customization

### Environment-Specific Paths
The `openBIM()` function contains **hardcoded paths** that must be adjusted for your environment. If these paths are incorrect, the script will fall back to opening a generic BIM web page.

### Assumptions (Hardcoded Dimensions)
The script relies on identifying components based on strict dimensional matching (using an internal tolerance). These values must match your panel system's specifications:

| Component | Target Thickness (Inches) |
| :--- | :--- |
| Foam | $3.000$ |
| Stud | $6.000$ |
| Track | $6.143$ |
| Sheathing | $0.625$ |

### Missing Features (TODOs)
The following functionality is identified in the script but not yet fully implemented:

* **Robust Foam Detection:** Finding the foam body without relying solely on the $3.0"$ thickness.
* **Sheathing/Frame Error Test:** A comprehensive test to compare sheathing geometry against the frame.
* **Automatic "L" Notches:** Scripting for automating the cutting of "L" shape notches in the back of the sheathing.
* **Window Bevel Toolpath:** Logic to detect windows under foam and apply the necessary bevel toolpath.
