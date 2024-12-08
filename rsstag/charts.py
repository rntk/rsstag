from typing import List, Tuple

def create_svg_histogram(data: List[Tuple[str, int]]) -> str:
    """
    Author: ChatGPT
    Creates an SVG histogram with bars extending to both sides of a central axis.

    Parameters:
        data (list of tuples): Each tuple contains a word (str) and its frequency (int).
    """
    # Sort data by frequency for better layout
    data = sorted(data, key=lambda x: x[1], reverse=True)

    # Split data into two halves for left and right bars
    left_data = []
    right_data = []
    for i, (word, frequency) in enumerate(data):
        if i % 2 == 0:
            left_data.append((word, frequency))
        else:
            right_data.append((word, frequency))

    # SVG dimensions and bar properties
    width = 1024
    bar_height = 20
    margin = 5
    text_width = 150  # Space reserved for text
    max_bar_length = (width - text_width * 2 - margin * 2) // 2  # Bars split on both sides
    max_frequency = max(f for _, f in data)
    height = (bar_height + margin) * max(len(left_data), len(right_data)) + margin

    # Start creating the SVG content
    svg_content = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
    ]

    y_offset = margin

    for i in range(max(len(left_data), len(right_data))):
        # Left side bar
        if i < len(left_data):
            word, frequency = left_data[i]
            bar_length = (frequency / max_frequency) * max_bar_length

            # Draw bar
            svg_content.append(
                f'<rect x="{text_width + max_bar_length - bar_length}" y="{y_offset}" width="{bar_length}" height="{bar_height}" fill="orange" />'
            )

            # Add word label aligned to the right with frequency
            svg_content.append(
                f'<text x="{text_width + max_bar_length - bar_length - 5}" y="{y_offset + bar_height - 4}" fill="black" font-size="12" text-anchor="end">{word} ({frequency})</text>'
            )

        # Right side bar
        if i < len(right_data):
            word, frequency = right_data[i]
            bar_length = (frequency / max_frequency) * max_bar_length

            # Draw bar
            svg_content.append(
                f'<rect x="{text_width + max_bar_length}" y="{y_offset}" width="{bar_length}" height="{bar_height}" fill="purple" />'
            )

            # Add word label with frequency
            svg_content.append(
                f'<text x="{text_width + max_bar_length + bar_length + 5}" y="{y_offset + bar_height - 4}" fill="black" font-size="12">{word} ({frequency})</text>'
            )

        # Move to the next bar position
        y_offset += bar_height + margin

    # Draw central axis
    svg_content.append(
        f'<line x1="{text_width + max_bar_length}" y1="0" x2="{text_width + max_bar_length}" y2="{height}" stroke="black" stroke-width="1" />'
    )

    # Close SVG
    svg_content.append("</svg>")

    return "\n".join(svg_content)