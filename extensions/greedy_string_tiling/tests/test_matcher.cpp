#include "gst.hpp"
#define CATCH_CONFIG_MAIN
#include "catch.hpp"


SCENARIO("Proper substrings of simple strings produces always at least one match when the minimum match length is half of the substring.", "[match-simple]") {
    const auto pattern_size = 4lu;
    const auto min_match_length = pattern_size >> 1;
    const std::string text = "abcdefghijklmnopqrst";
    const std::string text_marks(text.size(), '0');
    const std::string pattern_marks(pattern_size, '0');

    GIVEN("The pattern is a prefix of some string.") {
        const std::string pattern = text.substr(0, pattern_size);

        WHEN("Calling match_strings with the given parameters") {
            const auto tiles = match_strings(pattern, text, min_match_length, text_marks, pattern_marks);

            REQUIRE(tiles.size() == 1);
            for (auto& tile : tiles) {
                REQUIRE(pattern.substr(tile.pattern_index, tile.match_length)
                        == text.substr(tile.text_index, tile.match_length));
            }
        }
    }

    GIVEN("The pattern is a suffix of some string.") {
        const std::string pattern = text.substr(text.size() - pattern_size, pattern_size);

        WHEN("Calling match_strings with the given parameters") {
            const auto tiles = match_strings(pattern, text, min_match_length, text_marks, pattern_marks);

            REQUIRE(tiles.size() == 1);
            for (auto& tile : tiles) {
                REQUIRE(pattern.substr(tile.pattern_index, tile.match_length)
                        == text.substr(tile.text_index, tile.match_length));
            }
        }
    }

    GIVEN("The pattern is an infix of some string.") {
        const std::string pattern = text.substr((text.size() >> 1) - pattern_size, pattern_size);

        WHEN("Calling match_strings with the given parameters") {
            const auto tiles = match_strings(pattern, text, min_match_length, text_marks, pattern_marks);

            REQUIRE(tiles.size() == 1);
            for (auto& tile : tiles) {
                REQUIRE(pattern.substr(tile.pattern_index, tile.match_length)
                        == text.substr(tile.text_index, tile.match_length));
            }
        }
    }

}


