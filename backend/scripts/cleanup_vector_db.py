import sys
import re
from pathlib import Path

# Thêm đường dẫn gốc để import được config
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qdrant_client import QdrantClient
from app.config import settings

def main():
    db_path = str(settings.qdrant_db_path)
    print(f"Đang kết nối tới Qdrant tại: {db_path}")
    
    try:
        client = QdrantClient(path=db_path)
    except Exception as e:
        print(f"Lỗi kết nối: {e}")
        return

    # Lấy danh sách các collection và alias
    collections = client.get_collections().collections
    aliases = client.get_aliases().aliases
    
    # Tạo mapping từ collection_name sang danh sách alias
    alias_map = {}
    for alias in aliases:
        if alias.collection_name not in alias_map:
            alias_map[alias.collection_name] = []
        alias_map[alias.collection_name].append(alias.alias_name)
    
    if not collections:
        print("Không có kho dữ liệu (collection) nào hiện tại.")
        return
        
    print("\n--- DANH SÁCH CÁC KHO DỮ LIỆU HIỆN CÓ ---")
    for i, c in enumerate(collections):
        alias_info = ""
        if c.name in alias_map:
            alias_info = f"  <-- ĐANG ĐƯỢC DÙNG (Alias: {', '.join(alias_map[c.name])})"
        print(f"{i + 1}. {c.name}{alias_info}")
        
    print("\nBạn muốn xóa kho dữ liệu nào?")
    print("(Nhập các số thứ tự cách nhau bằng khoảng trắng, VD: '1 3 4', hoặc ấn Enter để thoát)")
    choice = input("Lựa chọn của bạn: ").strip()
    
    if choice:
        # Tách các số bằng dấu phẩy hoặc khoảng trắng
        parts = re.split(r'[,\s]+', choice)
        indexes_to_delete = []
        for p in parts:
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < len(collections):
                    indexes_to_delete.append(idx)
        
        # Lọc bỏ trùng lặp
        indexes_to_delete = list(set(indexes_to_delete))
        
        if not indexes_to_delete:
            print("Không tìm thấy lựa chọn hợp lệ.")
            return
            
        targets = [collections[i].name for i in indexes_to_delete]
        
        print("\nCác kho sẽ bị xóa:")
        for t in targets:
            warning = " [CẢNH BÁO: ĐANG ĐƯỢC DÙNG]" if t in alias_map or t == "legal_docs" else ""
            print(f"- {t}{warning}")
            
        confirm = input("\nBạn có chắc chắn muốn xóa tất cả các kho trên? (y/n): ").strip().lower()
        if confirm == 'y':
            for t in targets:
                client.delete_collection(collection_name=t)
                print(f"[THÀNH CÔNG] Đã xóa kho '{t}'.")
        else:
            print("Đã hủy thao tác.")
    else:
        print("Đã thoát không xóa gì cả.")

if __name__ == "__main__":
    main()
