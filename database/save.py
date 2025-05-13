from database.trademark import upsert_trademark_master

def save_to_db(session, BrandModel, items, source):
    for item in items:
        brand = BrandModel(
            id=item["id"],
            name=item["name"],
            product_group=item["product_group"],
            status=item["status"],
            registration_date=item["registration_date"],
            image_url=item["image_url"],
            source=source
        )
        session.merge(brand)
        upsert_trademark_master(session.bind, item, source)
    session.commit()
