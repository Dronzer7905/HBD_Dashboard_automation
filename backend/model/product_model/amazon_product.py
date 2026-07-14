from extensions import db

class AmazonProduct(db.Model):
    __tablename__ = 'amazon_products'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    asin = db.Column(db.String(20))
    title = db.Column(db.String(1024))
    imgUrl = db.Column(db.String(1024))
    productUrl = db.Column(db.String(1024))
    stars = db.Column(db.Numeric(2, 1))
    reviews = db.Column(db.Integer)
    price = db.Column(db.Numeric(10, 2))
    listPrice = db.Column(db.Numeric(10, 2))
    categoryName = db.Column(db.String(255))
    isBestSeller = db.Column(db.Boolean)
    boughtInLastMonth = db.Column(db.Integer)

    def to_dict(self):
        return {
            "id": self.id,
            "asin": self.asin,
            "title": self.title,
            "imgUrl": self.imgUrl,
            "productUrl": self.productUrl,
            "stars": float(self.stars) if self.stars is not None else 0.0,
            "reviews": self.reviews,
            "price": float(self.price) if self.price is not None else 0.0,
            "listPrice": float(self.listPrice) if self.listPrice is not None else 0.0,
            "categoryName": self.categoryName,
            "isBestSeller": self.isBestSeller,
            "boughtInLastMonth": self.boughtInLastMonth
        }