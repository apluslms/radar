#include "gst.hpp"
#include "data_generator.hpp"
#define CATCH_CONFIG_MAIN
#include "catch.hpp"


SCENARIO("Proper substrings of simple strings produces always at least one match when the minimum match length is half of the substring.", "[match-simple]") {
    CAPTURE(data_generator_seed);

    constexpr auto pattern_size = 4lu;
    constexpr auto init_search_length = pattern_size >> 1;
    const std::string text = "abcdefghijklmnopqrst";

    GIVEN("The pattern is a prefix of some string.") {
        const std::string pattern = text.substr(0, pattern_size);

        WHEN("Calling match_strings with the given parameters") {
            const auto tiles = match_strings(pattern, text, init_search_length);

            THEN("There is only one match, which is the prefix") {
                REQUIRE(tiles.size() == 1);
                for (auto& tile : tiles) {
                    INFO(tile.pattern_index);
                    INFO(tile.text_index);
                    REQUIRE(pattern.substr(tile.pattern_index, tile.match_length)
                            == text.substr(tile.text_index, tile.match_length));
                }
            }
        }
    }

    GIVEN("The pattern is a suffix of some string.") {
        const std::string pattern = text.substr(text.size() - pattern_size, pattern_size);

        WHEN("Calling match_strings with the given parameters") {
            const auto tiles = match_strings(pattern, text, init_search_length);

            THEN("There is only one match, which is the suffix") {
                REQUIRE(tiles.size() == 1);
                for (auto& tile : tiles) {
                    REQUIRE(pattern.substr(tile.pattern_index, tile.match_length)
                            == text.substr(tile.text_index, tile.match_length));
                }
            }
        }
    }

    GIVEN("The pattern is an infix of some string.") {
        const std::string pattern = text.substr((text.size() >> 1) - pattern_size, pattern_size);

        WHEN("Calling match_strings with the given parameters") {
            const auto tiles = match_strings(pattern, text, init_search_length);

            THEN("There is only one match, which is the infix") {
                REQUIRE(tiles.size() == 1);
                for (auto& tile : tiles) {
                    REQUIRE(pattern.substr(tile.pattern_index, tile.match_length)
                            == text.substr(tile.text_index, tile.match_length));
                }
            }
        }
    }

}


SCENARIO("Proper substrings of simple strings produces always at least one match when the minimum match length is equal to the substring.", "[match-simple-exact]") {
    CAPTURE(data_generator_seed);

    constexpr auto pattern_size = 4lu;
    const std::string text = "abcdefghijklmnopqrst";
    constexpr auto init_search_length = pattern_size;

    GIVEN("The pattern is a prefix of some string.") {
        const std::string pattern = text.substr(0, pattern_size);

        WHEN("Calling match_strings with the given parameters") {
            const auto tiles = match_strings(pattern, text, init_search_length);

            THEN("There is only one match, which is the prefix") {
                REQUIRE(tiles.size() == 1);
                for (auto& tile : tiles) {
                    REQUIRE(pattern.substr(tile.pattern_index, tile.match_length)
                            == text.substr(tile.text_index, tile.match_length));
                }
            }
        }
    }

    GIVEN("The pattern is a suffix of some string.") {
        const std::string pattern = text.substr(text.size() - pattern_size, pattern_size);

        WHEN("Calling match_strings with the given parameters") {
            const auto tiles = match_strings(pattern, text, init_search_length);

            THEN("There is only one match, which is the suffix") {
                REQUIRE(tiles.size() == 1);
                for (auto& tile : tiles) {
                    REQUIRE(pattern.substr(tile.pattern_index, tile.match_length)
                            == text.substr(tile.text_index, tile.match_length));
                }
            }
        }
    }

    GIVEN("The pattern is an infix of some string.") {
        const std::string pattern = text.substr((text.size() >> 1) - pattern_size, pattern_size);

        WHEN("Calling match_strings with the given parameters") {
            const auto tiles = match_strings(pattern, text, init_search_length);

            THEN("There is only one match, which is the infix") {
                REQUIRE(tiles.size() == 1);
                for (auto& tile : tiles) {
                    REQUIRE(pattern.substr(tile.pattern_index, tile.match_length)
                            == text.substr(tile.text_index, tile.match_length));
                }
            }
        }
    }

}


SCENARIO("Strings that have no characters in common can never have matches", "[no-match-simple]") {
    CAPTURE(data_generator_seed);

    GIVEN("Two disjoint strings") {
        const std::string text = "abcdefghijklmnopqrst";
        const std::string pattern = "uvwxyz";
        const auto init_search_length = pattern.size() >> 1;

        WHEN("Calling match_strings with the given parameters") {
            const auto tiles = match_strings(pattern, text, init_search_length);

            THEN("There are no matches") {
                REQUIRE(tiles.size() == 0);
            }
        }
    }
}


SCENARIO("Proper substrings of random strings produces always at least one match when the minimum match length is less than the substring length", "[match-random]") {
    CAPTURE(data_generator_seed);

    GIVEN("one random string of size 100 and its substring") {
        const auto text_size = 100lu;
        const std::string text = next_string(text_size);

        const auto pattern_size = next_integer(1lu, text_size);
        const auto pattern_begin = next_integer(0lu, text_size - pattern_size);
        const std::string pattern = text.substr(pattern_begin, pattern_size);

        const auto init_search_length = next_integer(1lu, pattern_size);

        WHEN("Calling match_strings with the given parameters") {
            const auto& tiles = match_strings(pattern, text, init_search_length);

            THEN("There is at least one match") {
                REQUIRE(tiles.size() > 0);
                for (auto& tile : tiles) {
                    REQUIRE(pattern.substr(tile.pattern_index, tile.match_length)
                            == text.substr(tile.text_index, tile.match_length));
                }
            }
        }
    }
}
