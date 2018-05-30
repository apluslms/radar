#include <algorithm>
#include "gst.hpp"


inline bool is_unmarked(const Token& token) noexcept {
    return not token.mark;
}


inline bool is_a_match(const Token& pattern_tok, const Token& text_tok) noexcept {
    return is_unmarked(pattern_tok) and is_unmarked(text_tok) and pattern_tok.chr == text_tok.chr;
}


inline bool is_not_occluded(const Match& match) noexcept {
    return is_unmarked(match.pattern_it[match.match_length - 1])
           and is_unmarked(match.text_it[match.match_length - 1]);
}


template<typename InputIt, typename T>
inline bool is_non_overlapping(InputIt it_a, InputIt it_b, const T& offset) noexcept {
    return (it_a + offset - 1 < it_b) or (it_b + offset - 1 < it_a);
}


template<class Matches, class InputIt, class T>
inline void add_if_non_overlapping(Matches& matches, InputIt new_match_pattern_it, InputIt new_match_text_it, const T& maxmatch) noexcept {
    if (!matches.empty()) {
        // Iterate over all longest matches, i.e. start from the top of the stack
        for (auto it = matches.rbegin(); it != matches.rend(); ++it) {
            if (it->match_length < maxmatch) {
                // Reached a match that is not maximal, all matches beyond this point are shorter than maxmatch
                return;
            }
            if (is_non_overlapping(new_match_pattern_it, it->pattern_it, maxmatch)
                    and is_non_overlapping(new_match_text_it, it->text_it, maxmatch)) {
                // New non-overlapping match found
                break;
            }
        }
    }
    matches.push_back({ new_match_pattern_it, new_match_text_it, maxmatch });
}


template<class Tokens, class Matches, class T>
inline T scanpatterns(Tokens& pattern_marks, Tokens& text_marks, const T& minimum_match_length, Matches& matches) noexcept {

    T maxmatch = minimum_match_length;
    // Forward to first unmarked pattern position
    auto pattern_it = std::find_if(pattern_marks.begin(),
                                   pattern_marks.end(),
                                   is_unmarked);
    // Starting at the first unmarked pattern character, iterate over rest of the pattern
    for (; pattern_it != pattern_marks.end(); ++pattern_it) {
        // Forward to first unmarked text position
        auto text_it = std::find_if(text_marks.begin(),
                                    text_marks.end(),
                                    is_unmarked);
        // For each unmarked text character, try to find the longest matching substring
        for (; text_it != text_marks.end(); ++text_it) {
            auto pattern_jt = pattern_it;
            auto text_jt = text_it;
            T matching_chars = 0;
            // Starting at pattern_it and text_it, count the amount of consequtive, matching characters
            while (pattern_jt != pattern_marks.end() and text_jt != text_marks.end()
                   and is_a_match(*pattern_jt, *text_jt)) {
                ++matching_chars;
                ++pattern_jt;
                ++text_jt;
            }
            // Add new match if it is a maximal match
            if (matching_chars >= maxmatch) {
                // New match found, and the match contains at least as many characters as the longest match found so far
                if (matching_chars > maxmatch) {
                    // The new match is longer than found so far, clear all matches
                    maxmatch = matching_chars;
                    matches.clear();
                }
                // Record a match of length maxmatch,
                // starting at pattern_it and text_it
                add_if_non_overlapping(matches, pattern_it, text_it, maxmatch);
            }
        }
    }
    return maxmatch;
}


template<class Tokens, class Matches, class Tiles, class T>
inline T markarrays(Tokens& pattern_marks, Tokens& text_marks, const T& maxmatch, Matches& matches, Tiles& tiles) noexcept {

    // Forward to first match of length maxmatch
    auto by_match_length = [&maxmatch](const Match& match) {
        return match.match_length == maxmatch;
    };
    auto match_it = std::find_if(matches.begin(),
                                 matches.end(),
                                 by_match_length);

    // Mark all matches of length maxmatch
    T length_of_tokens_tiled = 0;

    for (; match_it != matches.end(); ++match_it) {
        if (is_not_occluded(*match_it)) {

            match_it->mark_all_tokens();
            length_of_tokens_tiled += maxmatch;

            // Get the starting indexes of this match in pattern and text
            const T& pattern_index = match_it->pattern_it - pattern_marks.begin();
            const T& text_index = match_it->text_it - text_marks.begin();
            tiles.push_back({ pattern_index, text_index, maxmatch });

        }
    }

    return length_of_tokens_tiled;
}


Tiles match_strings(const std::string& pattern, const std::string& text,
        const unsigned& minimum_match_length,
        const std::string& init_pattern_marks,
        const std::string& init_text_marks) noexcept {

    Tokens pattern_marks;
    pattern_marks.reserve(pattern.size());
    for (auto i = 0u; i < pattern.size(); ++i) {
        pattern_marks.push_back({ pattern[i], init_pattern_marks[i] == '1' });
    }

    Tokens text_marks;
    text_marks.reserve(text.size());
    for (auto i = 0u; i < text.size(); ++i) {
        text_marks.push_back({ text[i], init_text_marks[i] == '1' });
    }

    unsigned length_of_tokens_tiled = 0;
    unsigned maxmatch = minimum_match_length + 1;

    // Begin searching for all possible matching substrings, until the longest
    // possible, unseen, matching substrings are shorter or equal to minimum_match_length
    Tiles tiles;
    while (maxmatch > minimum_match_length) {
        std::vector<Match> matches;
        // Find all matching substrings and their lengths, and push the data to matches
        maxmatch = scanpatterns(pattern_marks, text_marks, minimum_match_length, matches);
        // Create new tiles by marking all unmarked tokens that participate in a maximal match of length maxmatch
        length_of_tokens_tiled += markarrays(pattern_marks, text_marks, maxmatch, matches, tiles);
    }

    return tiles;
}


