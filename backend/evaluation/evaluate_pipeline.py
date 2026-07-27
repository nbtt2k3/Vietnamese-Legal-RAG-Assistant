import json
import time
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from retrieval.pipeline import RetrievalPipeline
from app.logger import logger

def create_sample_dataset():
    """Tạo một dataset mẫu để đánh giá"""
    return [
        {
            "query": "Hợp đồng dân sự vô hiệu khi nào?",
            "expected_keywords": ["122", "123", "vô hiệu", "Bộ luật Dân sự"],
            "intent_type": "dieu_kien"
        },
        {
            "query": "Tôi sinh năm 2008 thì có được đứng tên mua đất không?",
            "expected_keywords": ["21", "năng lực hành vi", "dân sự", "đất đai"],
            "intent_type": "dieu_kien"
        }
    ]

async def run_evaluation():
    logger.info("Starting RAG Pipeline Evaluation (Benchmark)")
    
    pipeline = RetrievalPipeline()
    dataset = create_sample_dataset()
    
    total = len(dataset)
    success = 0
    total_latency = 0
    
    results = []
    
    for item in dataset:
        query = item["query"]
        logger.info(f"Evaluating query: {query}")
        
        t0 = time.time()
        # Dùng retrieval pipeline để đánh giá khả năng trích xuất
        # Gọi run() bằng asyncio.to_thread không cần thiết vì ta đang gọi trực tiếp
        # Nhưng để an toàn với synchronous code
        result = await asyncio.to_thread(pipeline.run, query=query)
        latency = time.time() - t0
        total_latency += latency
        
        # Đánh giá: 
        # 1. Intent đúng không?
        intent_match = result.query_intent.loai_yeu_cau == item["intent_type"]
        
        # 2. Có ứng viên (candidates) liên quan chứa expected keywords không?
        keyword_hits = 0
        for cand in result.candidates[:5]:
            text_lower = cand.text.lower()
            for kw in item["expected_keywords"]:
                if kw.lower() in text_lower:
                    keyword_hits += 1
                    break # hit ít nhất 1 keyword trong chunk này
        
        is_success = intent_match and keyword_hits > 0
        if is_success:
            success += 1
            
        results.append({
            "query": query,
            "latency": round(latency, 2),
            "intent_match": intent_match,
            "keyword_hits": keyword_hits,
            "success": is_success,
            "candidates_count": len(result.candidates)
        })
        
    avg_latency = total_latency / total if total > 0 else 0
    accuracy = (success / total) * 100 if total > 0 else 0
    
    logger.info(f"--- EVALUATION SUMMARY ---")
    logger.info(f"Total queries: {total}")
    logger.info(f"Accuracy: {accuracy:.1f}%")
    logger.info(f"Average latency: {avg_latency:.2f}s")
    
    # Save report
    report_path = Path(__file__).parent / "benchmark_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Report saved to {report_path}")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
