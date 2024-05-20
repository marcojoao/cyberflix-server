import concurrent.futures


def divide_chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i : i + n]


def parallel_for(function, items, **kwargs) -> list:
    items = list(items)
    results = [None for _ in range(len(items))]

    def __thread_job(index, item):
        return index, function(item=item, index=index, **kwargs)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(__thread_job, index, item) for index, item in enumerate(items)]

        for future in concurrent.futures.as_completed(futures):
            index, result = future.result()
            results[index] = result

    return results
