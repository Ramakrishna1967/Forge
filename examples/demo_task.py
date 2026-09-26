
def fib(n):
    a, b = 0, 1
    out = []
    for _ in range(n):
        out.append(a)
        a, b = b, a + b
    return out

if __name__ == "__main__":
    print(fib(10))
    assert fib(10) == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
    print("demo-ok")
