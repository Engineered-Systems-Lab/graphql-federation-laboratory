"""The scoring contract: how the harness calls a corpus's scoring module and what it accepts back.

The harness loads `scoring.py` from the corpus folder and calls it through one of two declared versions:

- Version 1, implicit (a module that declares nothing; study 1's corpus): `score(submission, schema, expected)`. Outcomes: correct,
  wrong_answer, format_error, silent_guess, definition_not_accepted.
- Version 2, declared by the module-level constant `SCORING_CONTRACT = 2` (corpus 2): `score(submission, schema, expected, context)`, where
  `context` holds the task id, set and category and the run's `ask_requester` log, the only source of a clarification. Outcomes: correct,
  wrong_answer, format_error, definition_not_accepted, abstained. For the ambiguity set it may also return the booleans `clarified` and
  `interpretationAccepted`, reported apart.

Every returned dict must carry `outcome` from its version's list and `score`, which is 1 exactly when the outcome is `correct`. A result that
breaks the contract raises ScoringContractError, which stops the study: a scorer defect is never recorded as a score.

The harness decides two outcomes itself, whatever the version: `did_not_finish` (no submission) and `vendor_error` (a vendor error that
failed again after its one requeue). `abstained` is incorrect for primary accuracy and reported as its own outcome; which submissions count as
abstention is decided by the corpus's own scorer and frozen with it.
"""
from study_common import sha256_file

OUTCOMES = {
    1: ('correct', 'wrong_answer', 'format_error', 'silent_guess', 'definition_not_accepted'),
    2: ('correct', 'wrong_answer', 'format_error', 'definition_not_accepted', 'abstained'),
}
CORRECT = ('correct',)
HARNESS_OUTCOMES = ('did_not_finish', 'vendor_error')
AMBIGUITY_FLAGS = ('clarified', 'interpretationAccepted')


class ScoringContractError(RuntimeError):
    """The scorer broke its declared contract; the study stops."""


class Contract:
    def __init__(self, module, path=None):
        version = getattr(module, 'SCORING_CONTRACT', 1)
        if isinstance(version, bool) or version not in OUTCOMES:
            raise ScoringContractError('The scorer declares SCORING_CONTRACT = %r; the harness knows versions %s'
                                       % (version, ', '.join(str(v) for v in sorted(OUTCOMES))))
        if not callable(getattr(module, 'score', None)):
            raise ScoringContractError('The scorer has no score function')
        self.module, self.version, self.path = module, version, path

    @property
    def outcomes(self):
        return OUTCOMES[self.version]

    def score(self, submission, task, context):
        """Score one submission of `task` (a dict with schema and expected). `context` is used by version 2 only."""
        if self.version == 1:
            result = self.module.score(submission, task['schema'], task['expected'])
        else:
            result = self.module.score(submission, task['schema'], task['expected'], dict(context))
        self.check(result)
        return result

    def check(self, result):
        if not isinstance(result, dict):
            raise ScoringContractError('The scorer returned %s, not a dict' % type(result).__name__)
        outcome = result.get('outcome')
        if outcome not in self.outcomes:
            raise ScoringContractError('The scorer returned the outcome %r, which contract version %d does not have (%s)'
                                       % (outcome, self.version, ', '.join(self.outcomes)))
        score = result.get('score')
        if isinstance(score, bool) or score not in (0, 1):
            raise ScoringContractError('The scorer returned the score %r; it must be 0 or 1' % (score,))
        if (score == 1) != (outcome in CORRECT):
            raise ScoringContractError('The scorer returned score %r with outcome %s; the score is 1 exactly when the outcome is correct'
                                       % (score, outcome))
        if self.version == 2:
            for flag in AMBIGUITY_FLAGS:
                if flag in result and not isinstance(result[flag], bool):
                    raise ScoringContractError('The scorer returned %s = %r; it must be true or false' % (flag, result[flag]))

    def describe(self):
        """The contract as the manifest records it."""
        out = {'version': self.version, 'outcomes': list(self.outcomes), 'correctOutcomes': list(CORRECT),
               'harnessOutcomes': list(HARNESS_OUTCOMES), 'notScored': ['budget_stop']}
        if self.version == 2:
            out['ambiguityFlags'] = list(AMBIGUITY_FLAGS)
        if self.path is not None:
            out['scorerSha256'] = sha256_file(self.path)
        return out
