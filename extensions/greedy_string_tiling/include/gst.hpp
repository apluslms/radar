#ifndef GST_H
#define GST_H
#include <string>
#include <vector>

struct Token {
    const char chr;
    bool mark;
};

typedef std::vector<Token> Tokens;

struct Match {
    typename Tokens::iterator pattern_it;
    typename Tokens::iterator text_it;
    unsigned match_length;

    inline void mark_all_tokens() const noexcept {
        for (auto i = 0u; i < match_length; ++i) {
            (pattern_it + i)->mark = true;
            (text_it + i)->mark = true;
        }
    };
};

struct Tile {
    unsigned pattern_index;
    unsigned text_index;
    unsigned match_length;
};

typedef std::vector<Tile> Tiles;

inline bool is_unmarked(const Token&) noexcept;

template<class InputIt, class T>
inline bool is_not_occluded(InputIt, InputIt, const T&) noexcept;

template<class InputIt, class T>
inline bool is_non_overlapping(InputIt, InputIt, const T&) noexcept;

template<class Matches, class InputIt, class T>
inline void add_non_overlapping_maxmatch(Matches&, InputIt, InputIt, const T&) noexcept;

template<class Tokens, class Matches, class T>
inline T scanpatterns(Tokens&, Tokens&, const T&, const T&, Matches&) noexcept;

template<class Tokens, class Matches, class Tiles, class T>
inline T markarrays(Tokens&, Tokens&, const T&, Matches&, Tiles&) noexcept;

Tiles match_strings(const std::string&, const std::string&, const unsigned&, const std::string&, const std::string&) noexcept;

#endif // GST_H
