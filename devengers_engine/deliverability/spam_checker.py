import re
from typing import Dict, Any, List

SPAM_KEYWORDS = [
    r"\bfree\b",
    r"\b100% free\b",
    r"\bact now\b",
    r"\bapply now\b",
    r"\bcash bonus\b",
    r"\bclick here\b",
    r"\bclick below\b",
    r"\bcongratulations\b",
    r"\bearn money\b",
    r"\bearn extra cash\b",
    r"\bguaranteed\b",
    r"\bincredible deal\b",
    r"\blimited time\b",
    r"\bmake money\b",
    r"\bmillion dollars\b",
    r"\bno catch\b",
    r"\bno cost\b",
    r"\bno experience\b",
    r"\bno risk\b",
    r"\border now\b",
    r"\bprize\b",
    r"\brisk free\b",
    r"\bsave big\b",
    r"\bspecial promotion\b",
    r"\burgent\b",
    r"\bwinner\b",
    r"\bwin big\b",
    r"\${2,}",
]


class SpamChecker:
    """Evaluates emails for spam filter triggers and deliverability optimization."""

    @classmethod
    def evaluate(cls, subject: str, html_body: str, text_body: str) -> Dict[str, Any]:
        """
        Calculates a deliverability score from 0 to 100.
        Returns:
            {
                "score": int (0-100),
                "rating": str,
                "issues": List[str],
                "recommendations": List[str],
                "details": Dict[str, Any]
            }
        """
        score = 100
        issues: List[str] = []
        recommendations: List[str] = []

        # 1. Subject Line Analysis
        clean_subj = subject.strip()
        if not clean_subj:
            score -= 30
            issues.append("Subject line is missing or empty.")
            recommendations.append("Provide a clear, engaging subject line (30-60 characters).")
        else:
            # Length check
            if len(clean_subj) < 10:
                score -= 10
                issues.append("Subject line is too short (< 10 chars).")
                recommendations.append("Expand subject to be more descriptive of the event or community update.")
            elif len(clean_subj) > 75:
                score -= 10
                issues.append("Subject line is long (> 75 chars) and may truncate on mobile screens.")
                recommendations.append("Shorten subject line to under 60 characters for best mobile preview.")

            # All-caps check in subject
            caps = sum(1 for c in clean_subj if c.isupper())
            letters = sum(1 for c in clean_subj if c.isalpha())
            if letters > 0 and (caps / letters) > 0.4:
                score -= 20
                issues.append("Subject line contains excessive capitalization (>40% uppercase).")
                recommendations.append("Use standard sentence or title casing. Avoid shouting in caps.")

            # Exclamation marks in subject
            excl_count = clean_subj.count("!")
            if excl_count > 1:
                score -= 15
                issues.append(f"Subject has {excl_count} exclamation marks.")
                recommendations.append("Use at most one exclamation mark or avoid them in subject lines.")

            # Keyword checks in subject
            for pat in SPAM_KEYWORDS:
                if re.search(pat, clean_subj, re.IGNORECASE):
                    score -= 10
                    kw = pat.replace(r"\b", "")
                    issues.append(f"Spam-flagged word '{kw}' detected in subject.")
                    recommendations.append(f"Rephrase '{kw}' in the subject line.")
                    break

        # 2. Body Text Analysis
        combined_text = (text_body + " " + clean_subj).lower()

        matched_spam_words = []
        for pat in SPAM_KEYWORDS:
            matches = re.findall(pat, combined_text, re.IGNORECASE)
            if matches:
                matched_spam_words.append(matches[0])

        if len(matched_spam_words) >= 3:
            deduction = min(30, len(matched_spam_words) * 7)
            score -= deduction
            issues.append(f"Multiple spam keywords detected in body: {', '.join(set(matched_spam_words))}")
            recommendations.append("Reduce high-pressure sales/promotional terminology.")

        # 3. Text vs HTML Multi-part check
        if not text_body or len(text_body.strip()) < 20:
            score -= 25
            issues.append("Plain text alternative is missing or too short.")
            recommendations.append("Ensure a full plain-text version accompanies the HTML email.")

        # 4. Unsubscribe & Compliance Check
        has_unsub = "unsubscribe" in combined_text or "opt-out" in combined_text or "support@devengers.org" in combined_text
        if not has_unsub:
            score -= 15
            issues.append("No clear unsubscribe or support contact found in email body.")
            recommendations.append("Include an unsubscribe note and contact link in the footer.")

        # 5. Rating determination
        final_score = max(0, min(100, score))
        if final_score >= 90:
            rating = "Excellent"
        elif final_score >= 75:
            rating = "Good"
        elif final_score >= 60:
            rating = "Fair (Minor Spam Risk)"
        else:
            rating = "High Spam Risk"

        return {
            "score": final_score,
            "rating": rating,
            "issues": issues,
            "recommendations": recommendations,
            "details": {
                "subject_length": len(clean_subj),
                "spam_words_found": list(set(matched_spam_words)),
                "has_plain_text": bool(text_body and len(text_body.strip()) >= 20),
                "has_unsubscribe": has_unsub,
            },
        }
