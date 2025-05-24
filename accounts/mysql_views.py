import mysql.connector
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class ProductDataView(APIView):

    def get(self, request, barcode):
        try:
            connection = mysql.connector.connect(
                host="103.97.126.29",
                user="vvesnzbk_product_data",
                password="Nguyen2004nam@",
                database="vvesnzbk_product_data"
            )
            cursor = connection.cursor(dictionary=True)


            query = "SELECT * FROM product_data WHERE item_barcode LIKE %s"
            cursor.execute(query, (f"%{barcode}%",))

            results = cursor.fetchall()
            cursor.close()
            connection.close()

            if results:
                return Response({"message": "Product data retrieved successfully", "data": results}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No product found"}, status=status.HTTP_404_NOT_FOUND)

        except mysql.connector.Error as err:
            return Response({"error": str(err)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProductListView(APIView):
    def get(self, request):
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        offset = (page - 1) * page_size

        try:
            connection = mysql.connector.connect(
                host="103.97.126.29",
                user="vvesnzbk_product_data",
                password="Nguyen2004nam@",
                database="vvesnzbk_product_data"
            )
            cursor = connection.cursor(dictionary=True)

            cursor.execute("SELECT COUNT(*) as total FROM product_data")
            total_items = cursor.fetchone()['total']

            query = f"SELECT * FROM product_data LIMIT {page_size} OFFSET {offset}"
            cursor.execute(query)
            results = cursor.fetchall()

            cursor.close()
            connection.close()

            return Response({
                "message": "Product list retrieved successfully",
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": (total_items + page_size - 1) // page_size,
                "data": results
            }, status=status.HTTP_200_OK)

        except mysql.connector.Error as err:
            return Response({"error": str(err)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
