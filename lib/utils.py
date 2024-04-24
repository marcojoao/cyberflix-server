import concurrent.futures


def divide_chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i : i + n]


def parallel_for(function, items, **kwargs) -> list:
    results = []
    order = []

    def __thread_job(index, item):
        return index, function(item=item, index=index, **kwargs)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(__thread_job, index, item) for index, item in enumerate(items)]

        for future in concurrent.futures.as_completed(futures):
            index, result = future.result()
            order.append(index)
            results.append(result)

        temp = [results[i] for i in order]
        results = temp

    return results
