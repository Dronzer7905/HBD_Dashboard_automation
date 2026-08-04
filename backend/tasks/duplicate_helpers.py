from sqlalchemy import func
from sqlalchemy.orm import Session
from model.item_csv_model import ItemData

DUPLICATE_KEY_COLUMNS = [
    ItemData.name, ItemData.category, ItemData.sub_category,
    ItemData.email, ItemData.city, ItemData.area, ItemData.address,
]

def get_duplicate_group_keys(db: Session):
    return (
        db.query(*DUPLICATE_KEY_COLUMNS, func.count(ItemData.id).label("cnt"))
        .filter(
            ItemData.name.isnot(None), func.trim(ItemData.name) != '',
            ItemData.address.isnot(None), func.trim(ItemData.address) != ''
        )
        .group_by(*DUPLICATE_KEY_COLUMNS)
        .having(func.count(ItemData.id) > 1)
    )

def get_group_members(db: Session, key: tuple):
    name, category, sub_category, email, city, area, address = key
    return (
        db.query(ItemData)
        .filter(
            ItemData.name == name, ItemData.category == category,
            ItemData.sub_category == sub_category, ItemData.email == email,
            ItemData.city == city, ItemData.area == area, ItemData.address == address,
        )
        .order_by(ItemData.id)
        .all()
    )
