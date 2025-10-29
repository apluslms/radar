# Helper function to swap start positions of matches.
def swap_positions(matches_list: list[list[int]]) -> list[list[int]]:
    for match in matches_list:
        swap = match[0]
        match[0] = match[1]
        match[1] = swap
    return matches_list
