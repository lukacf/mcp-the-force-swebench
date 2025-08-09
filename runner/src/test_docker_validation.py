#!/usr/bin/env python3
"""Test Docker evaluation with an Astropy instance."""

import json
import logging

from evaluator import evaluate_patch_docker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Use the Astropy instance we already have
    instance_json = """{"instance_id": "astropy__astropy-12907", "problem_statement": "Modeling's `separability_matrix` does not compute separability correctly for nested CompoundModels\\nConsider the following model:\\r\\n\\r\\n```python\\r\\nfrom astropy.modeling import models as m\\r\\nfrom astropy.modeling.separable import separability_matrix\\r\\n\\r\\ncm = m.Linear1D(10) & m.Linear1D(5)\\r\\n```\\r\\n\\r\\nIt's separability matrix as you might expect is a diagonal:\\r\\n\\r\\n```python\\r\\n>>> separability_matrix(cm)\\r\\narray([[ True, False],\\r\\n       [False,  True]])\\r\\n```\\r\\n\\r\\nIf I make the model more complex:\\r\\n```python\\r\\n>>> separability_matrix(m.Pix2Sky_TAN() & m.Linear1D(10) & m.Linear1D(5))\\r\\narray([[ True,  True, False, False],\\r\\n       [ True,  True, False, False],\\r\\n       [False, False,  True, False],\\r\\n       [False, False, False,  True]])\\r\\n```\\r\\n\\r\\nThe output matrix is again, as expected, the outputs and inputs to the linear models are separable and independent of each other.\\r\\n\\r\\nIf however, I nest these compound models:\\r\\n```python\\r\\n>>> separability_matrix(m.Pix2Sky_TAN() & cm)\\r\\narray([[ True,  True, False, False],\\r\\n       [ True,  True, False, False],\\r\\n       [False, False,  True,  True],\\r\\n       [False, False,  True,  True]])\\r\\n```\\r\\nSuddenly the inputs and outputs are no longer separable?\\r\\n\\r\\nThis feels like a bug to me, but I might be missing something?\\n", "repo": "astropy/astropy", "base_commit": "d16bfe05a744909de4b27f5875fe0d4ed41ce607", "patch": "diff --git a/astropy/modeling/separable.py b/astropy/modeling/separable.py\\n--- a/astropy/modeling/separable.py\\n+++ b/astropy/modeling/separable.py\\n@@ -242,7 +242,7 @@ def _cstack(left, right):\\n         cright = _coord_matrix(right, 'right', noutp)\\n     else:\\n         cright = np.zeros((noutp, right.shape[1]))\\n-        cright[-right.shape[0]:, -right.shape[1]:] = 1\\n+        cright[-right.shape[0]:, -right.shape[1]:] = right\\n \\n     return np.hstack([cleft, cright])\\n \\n", "test_patch": "diff --git a/astropy/modeling/tests/test_separable.py b/astropy/modeling/tests/test_separable.py\\n--- a/astropy/modeling/tests/test_separable.py\\n+++ b/astropy/modeling/tests/test_separable.py\\n@@ -28,6 +28,13 @@\\n p1 = models.Polynomial1D(1, name='p1')\\n \\n \\n+cm_4d_expected = (np.array([False, False, True, True]),\\n+                  np.array([[True,  True,  False, False],\\n+                            [True,  True,  False, False],\\n+                            [False, False, True,  False],\\n+                            [False, False, False, True]]))\\n+\\n+\\n compound_models = {\\n     'cm1': (map3 & sh1 | rot & sh1 | sh1 & sh2 & sh1,\\n             (np.array([False, False, True]),\\n@@ -52,7 +59,17 @@\\n     'cm7': (map2 | p2 & sh1,\\n             (np.array([False, True]),\\n              np.array([[True, False], [False, True]]))\\n-            )\\n+            ),\\n+    'cm8': (rot & (sh1 & sh2), cm_4d_expected),\\n+    'cm9': (rot & sh1 & sh2, cm_4d_expected),\\n+    'cm10': ((rot & sh1) & sh2, cm_4d_expected),\\n+    'cm11': (rot & sh1 & (scl1 & scl2),\\n+             (np.array([False, False, True, True, True]),\\n+              np.array([[True,  True,  False, False, False],\\n+                        [True,  True,  False, False, False],\\n+                        [False, False, True,  False, False],\\n+                        [False, False, False, True,  False],\\n+                        [False, False, False, False, True]]))),\\n }\\n \\n \\n"}"""
    
    instance = json.loads(instance_json)
    
    logger.info("Testing Docker evaluation for Astropy instance")
    logger.info("=" * 60)
    
    # Test 1: Good patch should pass
    logger.info("TEST 1: Good patch (should PASS)")
    logger.info("=" * 60)
    
    result = evaluate_patch_docker(instance, instance['patch'])
    
    if result['passed']:
        logger.info("✅ GOOD PATCH PASSED - Correct!")
    else:
        logger.error(f"❌ GOOD PATCH FAILED - Incorrect! Error: {result['error']}")
        logger.error(f"Test output:\n{result.get('test_output', 'No output')}")
    
    # Test 2: Empty patch should fail
    logger.info("=" * 60)
    logger.info("TEST 2: Empty patch (should FAIL)")
    logger.info("=" * 60)
    
    result = evaluate_patch_docker(instance, "")
    
    if not result['passed']:
        logger.info("✅ EMPTY PATCH FAILED - Correct!")
    else:
        logger.error("❌ EMPTY PATCH PASSED - Incorrect!")
        logger.error(f"Test output:\n{result.get('test_output', 'No output')}")
    
    logger.info("=" * 60)
    logger.info("DOCKER VALIDATION COMPLETE")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()