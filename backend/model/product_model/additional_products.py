from extensions import db

class Blinkit(db.Model):
    __tablename__ = 'blinkit'

    product_id = db.Column(db.BigInteger, primary_key=True)
    product_name = db.Column(db.Text)
    brand = db.Column(db.String(255))
    category = db.Column(db.String(255))
    sub_category = db.Column(db.String(255))
    price = db.Column(db.Numeric(10, 2))
    mrp = db.Column(db.Numeric(10, 2))
    discount = db.Column(db.Numeric(10, 2))
    quantity = db.Column(db.String(100))
    availability = db.Column(db.Boolean)
    image_url = db.Column(db.Text)
    product_url = db.Column(db.Text)

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "brand": self.brand,
            "category": self.category,
            "sub_category": self.sub_category,
            "price": float(self.price) if self.price else 0,
            "mrp": float(self.mrp) if self.mrp else 0,
            "discount": float(self.discount) if self.discount else 0,
            "quantity": self.quantity,
            "availability": bool(self.availability),
            "image_url": self.image_url,
            "product_url": self.product_url
        }

class DMart(db.Model):
    __tablename__ = 'dmart_products'
    id = db.Column(db.Integer, primary_key=True)
    asin = db.Column(db.String(100))
    title = db.Column(db.Text)
    imgUrl = db.Column(db.Text)
    productUrl = db.Column(db.Text)
    stars = db.Column(db.String(50))
    reviews = db.Column(db.String(50))
    price = db.Column(db.String(100))
    listPrice = db.Column(db.String(100))
    categoryName = db.Column(db.String(255))
    isBestSeller = db.Column(db.String(50))
    boughtInLastMonth = db.Column(db.String(100))

    def to_dict(self):
        return {
            "id": self.id,
            "asin": self.asin,
            "name": self.title,
            "price": self.price,
            "list_price": self.listPrice,
            "stars": self.stars,
            "reviews": self.reviews,
            "category": self.categoryName,
            "link": self.productUrl
        }

class JioMart(db.Model):
    __tablename__ = 'jio_mart_products'
    id = db.Column(db.Integer, primary_key=True)
    asin = db.Column(db.String(100))
    title = db.Column(db.Text)
    imgUrl = db.Column(db.Text)
    productUrl = db.Column(db.Text)
    stars = db.Column(db.String(50))
    reviews = db.Column(db.String(50))
    price = db.Column(db.String(100))
    listPrice = db.Column(db.String(100))
    categoryName = db.Column(db.String(255))
    isBestSeller = db.Column(db.String(50))
    boughtInLastMonth = db.Column(db.String(100))

    def to_dict(self):
        return {
            "id": self.id,
            "asin": self.asin,
            "name": self.title,
            "price": self.price,
            "list_price": self.listPrice,
            "stars": self.stars,
            "reviews": self.reviews,
            "category": self.categoryName,
            "link": self.productUrl
        }

class Flipkart(db.Model):
    __tablename__ = 'flipkart_products'
    id = db.Column(db.Integer, primary_key=True)
    asin = db.Column(db.String(100))
    title = db.Column(db.Text)
    imgUrl = db.Column(db.Text)
    productUrl = db.Column(db.Text)
    stars = db.Column(db.String(50))
    reviews = db.Column(db.String(50))
    price = db.Column(db.String(100))
    listPrice = db.Column(db.String(100))
    categoryName = db.Column(db.String(255))
    isBestSeller = db.Column(db.String(50))
    boughtInLastMonth = db.Column(db.String(100))

    def to_dict(self):
        return {
            "id": self.id,
            "asin": self.asin,
            "name": self.title,
            "price": self.price,
            "list_price": self.listPrice,
            "stars": self.stars,
            "reviews": self.reviews,
            "category": self.categoryName,
            "link": self.productUrl
        }

class IndiaMart(db.Model):
    __tablename__ = 'india_mart'
    id = db.Column(db.Integer, primary_key=True)
    asin = db.Column(db.String(100))
    title = db.Column(db.Text)
    imgUrl = db.Column(db.Text)
    productUrl = db.Column(db.Text)
    stars = db.Column(db.String(50))
    reviews = db.Column(db.String(50))
    price = db.Column(db.String(100))
    listPrice = db.Column(db.String(100))
    categoryName = db.Column(db.String(255))
    isBestSeller = db.Column(db.String(50))
    boughtInLastMonth = db.Column(db.String(100))

    def to_dict(self):
        return {
            "id": self.id,
            "asin": self.asin,
            "name": self.title,
            "price": self.price,
            "list_price": self.listPrice,
            "stars": self.stars,
            "reviews": self.reviews,
            "category": self.categoryName,
            "link": self.productUrl
        }

class Vivo(db.Model):
    __tablename__ = 'vivo'
    id = db.Column(db.Integer, primary_key=True)
    pos_id = db.Column(db.String(100))
    hardware_id = db.Column(db.String(100))
    store_id = db.Column(db.String(100))
    merchant_name = db.Column(db.String(255))
    store_name = db.Column(db.String(255))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pin_code = db.Column(db.String(20))

    def to_dict(self):
        return {
            "id": self.id,
            "pos_id": self.pos_id,
            "merchant_name": self.merchant_name,
            "name": self.store_name,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "pin_code": self.pin_code
        }
