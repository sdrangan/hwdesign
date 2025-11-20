#include <iostream>

void simp_fun(int a, int b, int& c);

int main() {
    int c;
    int a = 7;
    int b = 5;
    int c_exp = a*b;
    simp_fun(a, b, c);
    std::cout << "Result: " << c << std::endl;

    if (c == c_exp)
        std::cout << "Test passed!" << std::endl;
    else
        std::cout << "Test failed!" << std::endl;
        
    return 0;
}