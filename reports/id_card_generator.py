import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from datetime import datetime
import json

def generate_qr_code(student_data, save_path):
    # Ensure directory exists
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(json.dumps({
        "ID": student_data['student_code'],
        "Name": student_data['name'],
        "Roll": student_data['roll_number'],
        "Check": "Verified AI Node"
    }))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(save_path)
    return save_path

def generate_id_card_image(student_data, photo_path, save_dir):
    """Generates an ID card as a PNG image."""
    os.makedirs(save_dir, exist_ok=True)
    width, height = 638, 1012 # CR80 300dpi approx
    img = Image.new('RGB', (width, height), color=(250, 250, 250))
    draw = ImageDraw.Draw(img)
    
    # Draw Background Styles
    # Top header bar
    draw.rectangle([0, 0, width, 180], fill=(26, 115, 232))
    
    # Load fonts (fallback to default if not found)
    try:
        font_large = ImageFont.truetype("arialbd.ttf", 46)
        font_medium = ImageFont.truetype("arialbd.ttf", 36)
        font_small = ImageFont.truetype("arial.ttf", 28)
    except IOError:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Header Text
    draw.text((width//2, 70), "SMART ATTENDANCE SYSTEM", fill="white", font=font_medium, anchor="mm")
    draw.text((width//2, 130), "STUDENT IDENTITY CARD", fill="white", font=font_small, anchor="mm")
    
    # Paste Photo
    if os.path.exists(photo_path):
        photo = Image.open(photo_path).convert("RGB")
        photo = photo.resize((300, 300))
        img.paste(photo, (width//2 - 150, 220))
        # Draw border around photo
        draw.rectangle([width//2 - 150, 220, width//2 + 150, 520], outline=(26, 115, 232), width=5)
        
    # Student Details
    y_offset = 580
    draw.text((width//2, y_offset), student_data['name'].upper(), fill=(0, 0, 0), font=font_large, anchor="mm")
    y_offset += 70
    
    details = []
    if student_data.get('university'):
        details.append(student_data['university'].upper())
    if student_data.get('school'):
        details.append(student_data['school'].upper())
    details.extend([
        f"ID: {student_data['student_code']}",
        f"ROLL: {student_data['roll_number']}",
        f"SECTION: {student_data['section']}"
    ])
    
    for detail in details:
        draw.text((width//2, y_offset), detail, fill=(50, 50, 50), font=font_small, anchor="mm")
        y_offset += 35
        
    # QR Code
    qr_path = os.path.join(save_dir, f"{student_data['student_code']}_qr.png")
    generate_qr_code(student_data, qr_path)
    qr_img = Image.open(qr_path)
    qr_img = qr_img.resize((150, 150))
    img.paste(qr_img, (width//2 - 75, y_offset + 20))
    
    # Footer
    draw.rectangle([0, height-60, width, height], fill=(5, 7, 13))
    
    # Save Image
    out_img_path = os.path.join(save_dir, f"{student_data['student_code']}_idcard.png")
    img.save(out_img_path)
    
    return out_img_path

def generate_id_card_pdf(image_path, save_dir, student_code):
    """Wraps the generated ID Card image into a PDF."""
    out_pdf_path = os.path.join(save_dir, f"{student_code}_idcard.pdf")
    # CR80 dimensions in points (approx 2.125 x 3.375 inches -> 153 x 243 points)
    c = canvas.Canvas(out_pdf_path, pagesize=(153, 243))
    c.drawImage(image_path, 0, 0, width=153, height=243)
    c.save()
    return out_pdf_path

def create_student_id_card(student_data, photo_path):
    from config import settings
    save_dir = settings.ID_CARD_DIR
    os.makedirs(save_dir, exist_ok=True)
    
    img_path = generate_id_card_image(student_data, photo_path, save_dir)
    pdf_path = generate_id_card_pdf(img_path, save_dir, student_data['student_code'])
    
    # Return relative URLs for web access (relative to project root/static)
    base_url = "static/id_cards/"
    return {
        "image_url": f"/{base_url}{os.path.basename(img_path)}",
        "pdf_url": f"/{base_url}{os.path.basename(pdf_path)}"
    }
