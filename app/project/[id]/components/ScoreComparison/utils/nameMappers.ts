// /ScoreComparison/utils/nameMappers.ts

/**
 * Maps short perturbation names to their full display names
 */
export const getPerturbationDisplayName = (perturbation: string): string => {
    // Map for short codes to full names
    const perturbationMap: Record<string, string> = {
        'robust': 'Robustness',
        'vocab': 'Vocabulary',
    };

    // Return the mapped name if available, otherwise use the original with first letter capitalized
    return perturbationMap[perturbation.toLowerCase()] ||
        (perturbation.charAt(0).toUpperCase() + perturbation.slice(1));
};