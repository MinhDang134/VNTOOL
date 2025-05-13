from bs4 import BeautifulSoup

def parse_wipo_html(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []

    result_blocks = soup.select("li.result-viewed")

    for block in result_blocks:
        try:
            brand_name = block.select_one("div.brandName").text.strip()
        except:
            brand_name = ""

        try:
            owner = block.select_one(".owner span.value").text.strip()
        except:
            owner = ""

        try:
            status = block.select_one(".status .value").text.strip()
        except:
            status = ""

        try:
            registration_date = block.select_one(".status .value").text.strip().split("(")[-1].rstrip(")")
        except:
            registration_date = ""

        try:
            image_tag = block.select_one("img")
            image_url = image_tag["src"] if image_tag else ""
        except:
            image_url = ""

        try:
            product_group = block.select_one(".label.niceclass + span.value").text.strip()
        except:
            product_group = ""

        try:
            number = block.select_one(".number span.value").text.strip()
        except:
            number = ""

        items.append({
            "id": number or brand_name + owner,
            "name": brand_name,
            "product_group": product_group,
            "status": status,
            "registration_date": registration_date,
            "image_url": image_url
        })

    return items
