from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from unidecode import unidecode
from .models import ProductData


class ProductDataView(APIView):
    def get(self, request, barcode):
        try:
            products = ProductData.objects.filter(item_barcode__icontains=barcode).values()
            if products:
                return Response({
                    "message": "Product data retrieved successfully",
                    "data": list(products)
                }, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No product found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as err:
            return Response({"error": str(err)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductSearchView(APIView):
    def get(self, request):
        search_text = request.GET.get('text', '').strip()
        if not search_text:
            return Response({"error": "Search text is required"}, status=status.HTTP_400_BAD_REQUEST)

        normalized_search_text = unidecode(search_text).lower()
        search_words = normalized_search_text.split()

        try:
            # Check if the search text is numeric
            if search_text.isdigit():
                # Search by item_code
                matching_products = list(ProductData.objects.filter(item_code=search_text).values("id", "item_barcode", "item_name"))

                if not matching_products:
                    # Fallback: Search by substring in barcode
                    matching_products = list(ProductData.objects.filter(item_barcode__icontains=search_text).values("id", "item_barcode", "item_name"))
            else:
                # Fallback to name search with multi-word support
                all_products = ProductData.objects.all().values("id", "item_barcode", "item_name")
                matching_products = []
                for product in all_products:
                    name = product.get("item_name", "")
                    normalized_name = unidecode(name).lower()
                    if all(word in normalized_name for word in search_words):
                        matching_products.append(product)

            if matching_products:
                return Response({
                    "message": "Search completed successfully",
                    "search_text": search_text,
                    "data": matching_products
                }, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No product found matching the search text"}, status=status.HTTP_404_NOT_FOUND)

        except Exception as err:
            return Response({"error": str(err)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductDetailView(APIView):
    def get(self, request, id):
        try:
            product = ProductData.objects.filter(id=id).values().first()
            if product:
                return Response({
                    "message": "Product data retrieved successfully",
                    "data": product
                }, status=status.HTTP_200_OK)
            else:
                return Response({"message": "No product found with the given ID"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as err:
            return Response({"error": str(err)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
