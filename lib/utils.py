import concurrent.futures
import traceback
import logging
import os

log = logging.getLogger(__name__)

def divide_chunks(l, n):
    """
    Divide a list into chunks of size n.

    Args:
        l: List to divide
        n: Size of each chunk

    Returns:
        Generator yielding chunks of the list
    """
    for i in range(0, len(l), n):
        yield l[i : i + n]


def parallel_for(function: callable, items: list[any], max_workers: int|None = None, **kwargs) -> list[any]:
    """
    Execute a function in parallel for a list of items with exact number of workers.

    Args:
        function: The function to execute for each item
        items: List of items to process
        max_workers: Maximum number of parallel workers to use
        **kwargs: Additional keyword arguments to pass to the function

    Returns:
        List of results in the same order as input items
    """
    # Add early return for empty items
    if not items:
        log.info("[yellow]No items to process, returning empty list")
        return []

    items = list(items)
    if len(items) == 0:
        log.info("[yellow]No items to process, returning empty list")
        return []
    # fallback workers according to cpu cores
    if max_workers is None or max_workers == 0:
        max_workers = os.cpu_count()
        log.info(f"[yellow]No max_workers provided, using {max_workers} workers")

    total_items = len(items)
    results = [None] * total_items

    # Adjust max_workers if we have fewer items than workers
    actual_workers = min(max_workers, total_items)

    # Create even distribution of items across workers
    batches = []
    items_per_worker = total_items // actual_workers
    extra_items = total_items % actual_workers

    start = 0
    for worker_id in range(actual_workers):
        # Calculate batch size for this worker
        batch_size = items_per_worker + (1 if worker_id < extra_items else 0)
        if batch_size > 0:
            end = start + batch_size
            batches.append((worker_id, start, end))
            start = end

    def process_batch(worker_id: int, start_idx: int, end_idx: int) -> list[tuple]:
        batch_results = []
        batch_items = items[start_idx:end_idx]

        for i, item in enumerate(batch_items):
            actual_idx = start_idx + i
            try:
                result = function(item, actual_idx, worker_id, **kwargs)
                batch_results.append((actual_idx, result))
            except Exception as e:
                log.info(f"[red]Error in worker {worker_id} processing item {actual_idx}: {str(e)}")
                batch_results.append((actual_idx, {
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }))
        return batch_results

    # Print distribution information
    log.info(f"[yellow]Starting processing with {actual_workers} workers")
    log.info(f"[yellow]Total items: {total_items}")
    for worker_id, start, end in batches:
        log.info(f"[yellow]Worker {worker_id} assigned items {start}-{end-1} ({end-start} items)")

    with concurrent.futures.ThreadPoolExecutor(max_workers=actual_workers) as executor:
        futures = []

        # Submit batches to executor
        for worker_id, start, end in batches:
            futures.append(executor.submit(process_batch, worker_id, start, end))

        # Collect results
        for future in concurrent.futures.as_completed(futures):
            try:
                for idx, result in future.result():
                    results[idx] = result
            except Exception as e:
                log.info(f"[red]Error collecting results: {str(e)}")
                raise

    log.info("[green]All processing completed!")
    return results
