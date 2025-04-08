from PIL import Image

def make_background_transparent(image_path, output_path):
    # Open the image
    img = Image.open(image_path).convert("RGBA")

    # Get the pixel data
    data = img.getdata()

    # Create a new list for modified pixels
    new_data = []

    # Check each pixel
    for item in data:
        # If the pixel is white (R=255, G=255, B=255)
        if item[0] == 255 and item[1] == 255 and item[2] == 255:
            # Make it transparent (alpha = 0)
            new_data.append((255, 255, 255, 0))
        else:
            # Keep the pixel unchanged
            new_data.append(item)

    # Apply the new pixel data
    img.putdata(new_data)

    # Save as PNG to preserve transparency
    img.save(output_path, "PNG")

# Replace with your file paths
make_background_transparent("//workspaces/195908002/surf-fishing-app/Striper_Log.png", "output.png")
