import winocr
from PIL import Image
import asyncio

async def test():
    img = Image.new('RGB', (100, 100), color=(255, 255, 255))
    result = await winocr.recognize_pil(img, 'en')
    print("Type of result:", type(result))
    print("Attributes in result:", dir(result))
    
    # Check lines
    if hasattr(result, 'lines'):
        print("Lines attribute found!")
        lines = list(result.lines)
        print("Number of lines:", len(lines))
        if len(lines) > 0:
            first_line = lines[0]
            print("Type of first line:", type(first_line))
            print("Attributes in first line:", dir(first_line))
            print("Text of first line:", first_line.text)
    
    # Check text
    if hasattr(result, 'lines'):
        full_text = " ".join([line.text for line in result.lines])
        print("Full OCR text:", full_text)

if __name__ == "__main__":
    asyncio.run(test())
