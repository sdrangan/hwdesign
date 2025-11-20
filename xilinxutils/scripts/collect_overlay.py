import os
import shutil
from pathlib import Path
from datetime import datetime

def main():
    project_dir = os.getcwd()
    base = os.path.basename(project_dir)
    overlay_dir = os.path.join(project_dir, "overlay")
    os.makedirs(overlay_dir, exist_ok=True)

    # Find .bit file containing "impl_1"
    bitfiles = sorted(Path(project_dir).rglob("*.bit"))
    bitfile = next((f for f in reversed(bitfiles) if "impl_1" in str(f)), None)

    if not bitfile:
        print(f"❌ No .bit file found in {project_dir}. Make sure synthesis and implementation are complete.")
        return
    

    # Derive base name and find .hwh file
    bitbase = bitfile.stem.replace("_wrapper", "")
    hwhfile = next((f for f in Path(project_dir).rglob(f"{bitbase}.hwh")), None)
    

    if not hwhfile:
        print(f"❌ No .hwh file found in {project_dir}. Make sure synthesis and implementation are complete.")
        return
    
    # Find .tcl file in same directory as .bit
    bitdir = bitfile.parent
    tclfile = next((f for f in bitdir.glob("*.tcl")), None)

    if not tclfile:
        print(f"❌ No .tcl file found in {bitdir}. Make sure synthesis and implementation are complete.")
        return
    

    # Copy and rename files
    bitfile_dst = os.path.join(overlay_dir, f"{base}.bit")
    hwhfile_dst = os.path.join(overlay_dir, f"{base}.hwh")
    tclfile_dst = os.path.join(overlay_dir, f"{base}.tcl")
    shutil.copy(bitfile, bitfile_dst)
    shutil.copy(hwhfile, hwhfile_dst)
    shutil.copy(tclfile, tclfile_dst)

    # Print file info
    print("Source file info:")
    for f in [bitfile, hwhfile, tclfile]:
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        print(f"  {f}")
        print(f"    Last modified: {mtime}")

    print(f"Overlay files copied to: {overlay_dir}/")
    print(f"  {base}.bit")
    print(f"  {base}.hwh")
    print(f"  {base}.tcl")

if __name__ == "__main__":
    main()