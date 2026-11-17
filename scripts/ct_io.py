"""We load the Case 1 CT from DICOM into a numpy volume in LPS millimetre space."""
import glob, numpy as np, pydicom

CT_DIR = "/private/tmp/claude-501/-Users-marcserrano--claude-spares-spare-KkTJPb/bced2654-ca10-4913-b69b-beeb349c481a/scratchpad/in/Case_001"


def load_ct(ct_dir=CT_DIR):
    files = glob.glob(ct_dir + "/*.dcm")
    slices = [pydicom.dcmread(f) for f in files]
    # we sort by position along the slice normal
    slices.sort(key=lambda s: float(s.ImagePositionPatient[2]))
    vol = np.stack([s.pixel_array.astype(np.int16) * float(s.RescaleSlope) + float(s.RescaleIntercept) for s in slices], axis=-1)
    vol = np.transpose(vol, (1, 0, 2)).astype(np.int16)  # we index as (i=col, j=row, k=slice)
    s0 = slices[0]
    spacing = np.array([float(s0.PixelSpacing[1]), float(s0.PixelSpacing[0]),
                        float(slices[1].ImagePositionPatient[2]) - float(s0.ImagePositionPatient[2])])
    origin = np.array([float(v) for v in s0.ImagePositionPatient])
    return vol, spacing, origin, s0
