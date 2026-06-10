import os
import cv2
import numpy as np
import re
from typing import Dict, Any


def preprocess_image(image_path: str) -> str:
    """
    Deskew, denoise, increase contrast.
    Returns path to cleaned image (saved as original_cleaned.ext).
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return image_path

    # Denoise
    img = cv2.bilateralFilter(img, 9, 75, 75)

    # Adaptive threshold for uneven lighting
    img = cv2.adaptiveThreshold(
        img,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2,
    )

    # Deskew
    coords = np.column_stack(np.where(img > 0))
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        img = cv2.warpAffine(
            img,
            m,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    root, ext = os.path.splitext(image_path)
    cleaned_path = f"{root}_cleaned{ext or '.jpg'}"
    cv2.imwrite(cleaned_path, img)
    return cleaned_path


def validate_extracted_data(data: Dict[str, Any], doc_type: str) -> Dict[str, Any]:
    """
    Validate fields based on document type.
    Adds keys: is_valid (bool), validation_errors (list)
    """
    errors = []
    doc = (doc_type or "").strip().lower()

    if doc == "lead":
        phone = data.get("phone", "")
        if phone and not re.fullmatch(r"\d{10}", re.sub(r"\D", "", str(phone))):
            errors.append("Invalid phone number (need 10 digits)")
            data["phone"] = None

        email = data.get("email", "")
        if email and not re.match(r"^[^@]+@[^@]+\.[^@]+$", str(email)):
            errors.append("Invalid email")
            data["email"] = None

    elif doc == "insurance":
        vin = data.get("vin", "")
        if vin and not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", str(vin), re.I):
            errors.append("Invalid VIN (must be 17 alphanumeric, no I/O/Q)")
            data["vin"] = None

        for field in ["effective_date", "expiration_date"]:
            val = data.get(field, "")
            if val and not re.match(r"\d{1,2}/\d{1,2}/\d{4}", str(val)):
                errors.append(f"Invalid {field} format (MM/DD/YYYY)")
                data[field] = None

    elif doc == "credit":
        ssn = data.get("ssn", "")
        if ssn and not re.fullmatch(r"\d{3}-\d{2}-\d{4}", str(ssn)):
            errors.append("Invalid SSN (format ###-##-####)")
            data["ssn"] = None

    data["is_valid"] = len(errors) == 0
    data["validation_errors"] = errors
    return data
