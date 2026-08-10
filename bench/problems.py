"""Subset propio estilo HumanEval (30 problemas). Evita depender del paquete human-eval.
Cada problema: prompt (firma + docstring) + test (codigo que hace assert sobre la funcion).
Cubre: strings, matematicas, listas/dicts, recursion, ordenacion/busqueda, bordes/errores."""

PROBLEMS = [
    # --- strings ---
    {
        "id": "reverse_words",
        "prompt": "def reverse_words(s: str) -> str:\n    \"\"\"Invierte el orden de las palabras en s, separadas por espacios.\"\"\"\n",
        "test": "assert reverse_words('hola mundo') == 'mundo hola'\nassert reverse_words('a b c') == 'c b a'",
    },
    {
        "id": "is_balanced",
        "prompt": "def is_balanced(s: str) -> bool:\n    \"\"\"Devuelve True si los parentesis '()' en s estan balanceados.\"\"\"\n",
        "test": "assert is_balanced('(())') == True\nassert is_balanced('(()') == False\nassert is_balanced('') == True",
    },
    {
        "id": "is_palindrome",
        "prompt": "def is_palindrome(s: str) -> bool:\n    \"\"\"Devuelve True si s es palindromo, ignorando mayusculas y espacios.\"\"\"\n",
        "test": "assert is_palindrome('Anita lava la tina') == True\nassert is_palindrome('hola') == False\nassert is_palindrome('') == True",
    },
    {
        "id": "count_vowels",
        "prompt": "def count_vowels(s: str) -> int:\n    \"\"\"Cuenta las vocales (a,e,i,o,u) en s, sin distinguir mayusculas.\"\"\"\n",
        "test": "assert count_vowels('Hola Mundo') == 4\nassert count_vowels('xyz') == 0",
    },
    {
        "id": "caesar_cipher",
        "prompt": "def caesar_cipher(s: str, shift: int) -> str:\n    \"\"\"Aplica un cifrado Cesar a s (solo letras minusculas a-z), desplazando shift posiciones.\"\"\"\n",
        "test": "assert caesar_cipher('abc', 1) == 'bcd'\nassert caesar_cipher('xyz', 3) == 'abc'",
    },
    {
        "id": "word_frequencies",
        "prompt": "def word_frequencies(s: str) -> dict:\n    \"\"\"Devuelve un dict palabra->numero de apariciones, separando por espacios.\"\"\"\n",
        "test": "assert word_frequencies('a b a c b a') == {'a': 3, 'b': 2, 'c': 1}",
    },
    {
        "id": "title_case",
        "prompt": "def title_case(s: str) -> str:\n    \"\"\"Pone en mayuscula la primera letra de cada palabra, resto en minuscula.\"\"\"\n",
        "test": "assert title_case('hola MUNDO') == 'Hola Mundo'\nassert title_case('') == ''",
    },
    {
        "id": "longest_word",
        "prompt": "def longest_word(s: str) -> str:\n    \"\"\"Devuelve la palabra mas larga de la frase s (la primera si hay empate).\"\"\"\n",
        "test": "assert longest_word('el gato negro corre') == 'negro'\nassert longest_word('a bb cc') == 'bb'",
    },
    # --- matematicas ---
    {
        "id": "is_prime",
        "prompt": "def is_prime(n: int) -> bool:\n    \"\"\"Devuelve True si n es primo, False si no.\"\"\"\n",
        "test": "assert is_prime(2) == True\nassert is_prime(1) == False\nassert is_prime(17) == True\nassert is_prime(18) == False",
    },
    {
        "id": "fibonacci",
        "prompt": "def fibonacci(n: int) -> int:\n    \"\"\"Devuelve el n-esimo numero de Fibonacci (fibonacci(0) == 0, fibonacci(1) == 1).\"\"\"\n",
        "test": "assert fibonacci(0) == 0\nassert fibonacci(1) == 1\nassert fibonacci(10) == 55",
    },
    {
        "id": "gcd",
        "prompt": "def gcd(a: int, b: int) -> int:\n    \"\"\"Devuelve el maximo comun divisor de a y b.\"\"\"\n",
        "test": "assert gcd(12, 18) == 6\nassert gcd(17, 5) == 1\nassert gcd(0, 5) == 5",
    },
    {
        "id": "is_perfect_square",
        "prompt": "def is_perfect_square(n: int) -> bool:\n    \"\"\"Devuelve True si n es un cuadrado perfecto.\"\"\"\n",
        "test": "assert is_perfect_square(16) == True\nassert is_perfect_square(15) == False\nassert is_perfect_square(0) == True",
    },
    {
        "id": "digital_root",
        "prompt": "def digital_root(n: int) -> int:\n    \"\"\"Suma repetidamente los digitos de n hasta obtener un solo digito.\"\"\"\n",
        "test": "assert digital_root(942) == 6\nassert digital_root(132189) == 6\nassert digital_root(0) == 0",
    },
    {
        "id": "roman_to_int",
        "prompt": "def roman_to_int(s: str) -> int:\n    \"\"\"Convierte un numeral romano (I,V,X,L,C,D,M) a entero.\"\"\"\n",
        "test": "assert roman_to_int('III') == 3\nassert roman_to_int('IX') == 9\nassert roman_to_int('LVIII') == 58\nassert roman_to_int('MCMXCIV') == 1994",
    },
    {
        "id": "collatz_length",
        "prompt": "def collatz_length(n: int) -> int:\n    \"\"\"Numero de pasos de la secuencia de Collatz hasta llegar a 1 (incluye el 1 inicial si n==1 -> 1).\"\"\"\n",
        "test": "assert collatz_length(1) == 1\nassert collatz_length(6) == 9",
    },
    # --- listas / dicts ---
    {
        "id": "flatten",
        "prompt": "def flatten(nested: list) -> list:\n    \"\"\"Aplana una lista de listas anidada a cualquier profundidad.\"\"\"\n",
        "test": "assert flatten([1, [2, 3], [4, [5, 6]]]) == [1, 2, 3, 4, 5, 6]\nassert flatten([]) == []",
    },
    {
        "id": "most_common",
        "prompt": "def most_common(items: list):\n    \"\"\"Devuelve el elemento mas frecuente de la lista (asume un unico maximo).\"\"\"\n",
        "test": "assert most_common([1, 2, 2, 3]) == 2\nassert most_common(['a', 'b', 'a']) == 'a'",
    },
    {
        "id": "dedupe_preserve_order",
        "prompt": "def dedupe_preserve_order(items: list) -> list:\n    \"\"\"Elimina duplicados de la lista manteniendo el primer orden de aparicion.\"\"\"\n",
        "test": "assert dedupe_preserve_order([1, 2, 1, 3, 2]) == [1, 2, 3]\nassert dedupe_preserve_order([]) == []",
    },
    {
        "id": "chunk_list",
        "prompt": "def chunk_list(items: list, size: int) -> list:\n    \"\"\"Divide items en sublistas de tamano size (la ultima puede ser mas corta).\"\"\"\n",
        "test": "assert chunk_list([1,2,3,4,5], 2) == [[1,2],[3,4],[5]]\nassert chunk_list([], 3) == []",
    },
    {
        "id": "merge_dicts_sum",
        "prompt": "def merge_dicts_sum(a: dict, b: dict) -> dict:\n    \"\"\"Combina dos dicts numero->numero, sumando los valores de claves compartidas.\"\"\"\n",
        "test": "assert merge_dicts_sum({'a':1,'b':2}, {'b':3,'c':4}) == {'a':1,'b':5,'c':4}",
    },
    {
        "id": "transpose",
        "prompt": "def transpose(matrix: list) -> list:\n    \"\"\"Transpone una matriz representada como lista de listas.\"\"\"\n",
        "test": "assert transpose([[1,2,3],[4,5,6]]) == [[1,4],[2,5],[3,6]]",
    },
    {
        "id": "group_by_parity",
        "prompt": "def group_by_parity(nums: list) -> dict:\n    \"\"\"Devuelve {'even': [...], 'odd': [...]} agrupando nums manteniendo el orden.\"\"\"\n",
        "test": "assert group_by_parity([1,2,3,4,5]) == {'even': [2,4], 'odd': [1,3,5]}",
    },
    {
        "id": "rotate_list",
        "prompt": "def rotate_list(items: list, k: int) -> list:\n    \"\"\"Rota la lista k posiciones a la derecha (k puede ser mayor que len(items)).\"\"\"\n",
        "test": "assert rotate_list([1,2,3,4,5], 2) == [4,5,1,2,3]\nassert rotate_list([1,2,3], 5) == [2,3,1]",
    },
    # --- recursion ---
    {
        "id": "factorial",
        "prompt": "def factorial(n: int) -> int:\n    \"\"\"Devuelve n! usando recursion.\"\"\"\n",
        "test": "assert factorial(0) == 1\nassert factorial(5) == 120",
    },
    {
        "id": "power_set",
        "prompt": "def power_set(items: list) -> list:\n    \"\"\"Devuelve todos los subconjuntos de items (lista de listas), incluyendo el vacio.\"\"\"\n",
        "test": "r = power_set([1,2])\nassert sorted([sorted(x) for x in r]) == [[], [1], [1,2], [2]]",
    },
    {
        "id": "binary_search",
        "prompt": "def binary_search(items: list, target) -> int:\n    \"\"\"Busqueda binaria sobre lista ordenada items. Devuelve el indice de target o -1.\"\"\"\n",
        "test": "assert binary_search([1,3,5,7,9], 7) == 3\nassert binary_search([1,3,5,7,9], 4) == -1",
    },
    # --- ordenacion / bordes / errores ---
    {
        "id": "quicksort",
        "prompt": "def quicksort(items: list) -> list:\n    \"\"\"Ordena items de menor a mayor usando el algoritmo quicksort.\"\"\"\n",
        "test": "assert quicksort([3,1,4,1,5,9,2,6]) == [1,1,2,3,4,5,6,9]\nassert quicksort([]) == []",
    },
    {
        "id": "safe_divide",
        "prompt": "def safe_divide(a: float, b: float):\n    \"\"\"Devuelve a/b, o None si b es 0 (sin lanzar excepcion).\"\"\"\n",
        "test": "assert safe_divide(10, 2) == 5\nassert safe_divide(1, 0) is None",
    },
    {
        "id": "second_largest",
        "prompt": "def second_largest(nums: list):\n    \"\"\"Devuelve el segundo valor mas grande distinto del maximo. None si no existe.\"\"\"\n",
        "test": "assert second_largest([1,5,3,5,2]) == 3\nassert second_largest([4,4,4]) is None",
    },
    {
        "id": "run_length_encode",
        "prompt": "def run_length_encode(s: str) -> str:\n    \"\"\"Codifica s por longitud de racha, ej 'aaabbc' -> 'a3b2c1'.\"\"\"\n",
        "test": "assert run_length_encode('aaabbc') == 'a3b2c1'\nassert run_length_encode('') == ''",
    },
]
