#include <cassert>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <limits>
#include <random>

#include "gst.hpp"
#include "data_generator.hpp"


struct Result {
    double min_time = std::numeric_limits<double>::max();
    double max_time = 0;
    double total_time = 0;
    match_length_t n = 0;
    match_length_t match_count = 0;
};

template<class T>
struct TestArgs {
    const T iterations;
    const T text_size;
    const T pattern_size;
    const float random_copy;
    explicit TestArgs(T a, T b, T c, float d) :
        iterations(a),
        text_size(b),
        pattern_size(c),
        random_copy(d) {}
};

std::ostream& operator<<(std::ostream& os, const Result& res) {
    auto avg = res.total_time / res.n;
    os << " min " << std::setprecision(3) << res.min_time
       << " max " << res.max_time
       << " avg " << avg
       << " total " << res.total_time
       << " ; with " << res.match_count << " string matches";
    return os;
}

template<class T>
Result bench_match_strings(const TestArgs<T>& args) {
    const auto init_search_length = std::min(20lu, args.pattern_size);
    auto iterations = args.iterations;
    Result res;

    while(iterations-- > 0) {
        const std::string text = next_string(args.text_size);
        const std::string pattern = random_string_copy(text, args.random_copy);

        auto start = std::chrono::high_resolution_clock::now();
        const auto& tiles = match_strings(pattern, text, init_search_length);
        auto end = std::chrono::high_resolution_clock::now();

        std::chrono::duration<double> elapsed = end - start;
        auto elapsed_c = elapsed.count();
        res.max_time = std::max(res.max_time, elapsed_c);
        res.min_time = std::min(res.min_time, elapsed_c);
        res.total_time += elapsed_c;
        res.n++;

        for (auto& tile : tiles) {
            const auto& pattern_str = pattern.substr(tile.pattern_index, tile.match_length);
            const auto& text_str = text.substr(tile.text_index, tile.match_length);
            if (pattern_str != text_str) {
                std::cerr << "FALSE MATCH\n" << pattern_str << "\n!=\n" << text_str << std::endl;
                assert(false);
            }
        }
        res.match_count += tiles.size();
    }

    return res;
}

int main() {
    std::cout << "Huge amount of tiny, random strings" << std::endl;
    {
        double total_time = 0;
        constexpr auto iterations = 2000;
        constexpr auto text_len = 20u;
        constexpr auto pattern_len = text_len;
        for (auto p = 0; p <= 4; ++p) {
            const float copy_prob = p / 4.0f;
            const TestArgs<match_length_t> args{ iterations, text_len, pattern_len, copy_prob};
            auto res = bench_match_strings(args);
            total_time += res.total_time;
            std::cout << "str similarity: " << std::setprecision(2) << copy_prob << res  << std::endl;
        }
        std::cout << "5 * " << iterations << " iterations, total (sec): " << std::setprecision(2) << total_time << std::endl;
        std::cout << std::endl;
    }

    std::cout << "Many short, random strings" << std::endl;
    {
        double total_time = 0;
        constexpr auto iterations = 300;
        constexpr auto text_len = 200lu;
        constexpr auto pattern_len = text_len;
        for (auto p = 0; p <= 4; ++p) {
            const float copy_prob = p / 4.0f;
            const TestArgs<match_length_t> args{ iterations, text_len, pattern_len, copy_prob};
            auto res = bench_match_strings(args);
            total_time += res.total_time;
            std::cout << "str similarity: " << std::setprecision(2) << copy_prob << res  << std::endl;
        }
        std::cout << "5 * " << iterations << " iterations, total (sec): " << std::setprecision(2) << total_time << std::endl;
        std::cout << std::endl;
    }

    std::cout << "Many average length random strings" << std::endl;
    {
        double total_time = 0;
        constexpr auto iterations = 300;
        constexpr auto text_len = 600lu;
        constexpr auto pattern_len = text_len;
        for (auto p = 0; p <= 4; ++p) {
            const float copy_prob = p / 4.0f;
            const TestArgs<match_length_t> args{ iterations, text_len, pattern_len, copy_prob};
            auto res = bench_match_strings(args);
            total_time += res.total_time;
            std::cout << "str similarity: " << std::setprecision(2) << copy_prob << res  << std::endl;
        }
        std::cout << "5 * " << iterations << " iterations, total (sec): " << std::setprecision(2) << total_time << std::endl;
        std::cout << std::endl;
    }

    std::cout << "Few very long random strings" << std::endl;
    {
        double total_time = 0;
        constexpr auto iterations = 50;
        constexpr auto text_len = 100000lu;
        constexpr auto pattern_len = text_len;
        for (auto p = 0; p <= 4; ++p) {
            const float copy_prob = p / 4.0f;
            const TestArgs<match_length_t> args{ iterations, text_len, pattern_len, copy_prob};
            auto res = bench_match_strings(args);
            total_time += res.total_time;
            std::cout << "str similarity: " << std::setprecision(2) << copy_prob << res  << std::endl;
        }
        std::cout << "5 * " << iterations << " iterations, total (sec): " << std::setprecision(2) << total_time << std::endl;
        std::cout << std::endl;
    }

}
