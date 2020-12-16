from typing import Set

import numpy as np

from obp import ope
from obp.ope import OffPolicyEvaluation
from obp.policy import BaseContextualPolicy
from obp.types import BanditFeedback


def test_fixture(
    synthetic_bandit_feedback: BanditFeedback,
    expected_reward_0: np.ndarray,
    feedback_key_set: Set[str],
    logistic_evaluation_policy: BaseContextualPolicy,
    random_action_dist: np.ndarray,
) -> None:
    """
    Check the validity of the fixture data generated by conftest.py
    """
    np.testing.assert_array_almost_equal(
        expected_reward_0, synthetic_bandit_feedback["expected_reward"][0]
    )
    assert feedback_key_set == set(
        synthetic_bandit_feedback.keys()
    ), f"Key set of bandit feedback should be {feedback_key_set}, but {synthetic_bandit_feedback.keys()}"
    assert synthetic_bandit_feedback["n_actions"] == len(
        logistic_evaluation_policy.model_list
    ), "model list length of logistic evaluation policy should be the same as n_actions"


def test_expected_value_of_random_evaluation_policy(
    synthetic_bandit_feedback: BanditFeedback, random_action_dist: np.ndarray
) -> None:
    """
    Test the performance of ope estimators using synthetic bandit data and random evaluation policy
    """
    expected_reward = np.expand_dims(
        synthetic_bandit_feedback["expected_reward"], axis=-1
    )
    action_dist = random_action_dist
    # compute ground truth policy value using expected reward
    ground_truth_policy_value = np.average(
        expected_reward[:, :, 0], weights=action_dist[:, :, 0], axis=1
    )
    # compute statistics of ground truth policy value
    gt_mean = ground_truth_policy_value.mean()
    gt_std = ground_truth_policy_value.std(ddof=1)
    # extract most of all estimators (ReplayMethod is not tested because it is out of scope; Switch-ipw(\tau=1) is not tested because it is known to be biased in this situation)
    all_estimators = ope.__all_estimators__
    estimators = [
        getattr(ope.estimators, estimator_name)()
        for estimator_name in all_estimators
        if estimator_name not in ["ReplayMethod", "SwitchInverseProbabilityWeighting"]
    ]
    # conduct OPE
    ope_instance = OffPolicyEvaluation(
        bandit_feedback=synthetic_bandit_feedback, ope_estimators=estimators
    )
    estimated_policy_value = ope_instance.estimate_policy_values(
        action_dist=action_dist, estimated_rewards_by_reg_model=expected_reward
    )
    # check the performance of OPE
    ci_bound = gt_std * 3 / np.sqrt(ground_truth_policy_value.shape[0])
    print(f"gt_mean: {gt_mean}, 3 * gt_std / sqrt(n): {ci_bound}")
    for key in estimated_policy_value:
        print(
            f"estimated_value: {estimated_policy_value[key]} ------ estimator: {key}, "
        )
        # test the performance of each estimator
        assert (
            np.abs(gt_mean - estimated_policy_value[key]) <= ci_bound
        ), f"OPE of {key} did not work well (absolute error is greator than 3*sigma)"


def test_response_format_using_random_evaluation_policy(
    synthetic_bandit_feedback: BanditFeedback, random_action_dist: np.ndarray
) -> None:
    """
    Test the response format of ope estimators using synthetic bandit data and random evaluation policy
    """
    expected_reward = np.expand_dims(
        synthetic_bandit_feedback["expected_reward"], axis=-1
    )
    action_dist = random_action_dist
    # extract most of all estimators (ReplayMethod is not tested because it is out of scope; Switch-ipw(\tau=1) is not tested because it is known to be biased in this situation)
    all_estimators = ope.__all_estimators__
    estimators = [
        getattr(ope.estimators, estimator_name)() for estimator_name in all_estimators
    ]
    # conduct OPE
    ope_instance = OffPolicyEvaluation(
        bandit_feedback=synthetic_bandit_feedback, ope_estimators=estimators
    )
    estimated_policy_value = ope_instance.estimate_policy_values(
        action_dist=action_dist, estimated_rewards_by_reg_model=expected_reward
    )
    estimated_intervals = ope_instance.estimate_intervals(
        action_dist=action_dist, estimated_rewards_by_reg_model=expected_reward
    )
    # check the format of OPE
    for key in estimated_policy_value:
        # check key of confidence intervals
        assert set(estimated_intervals[key].keys()) == set(
            ["mean", "95.0% CI (lower)", "95.0% CI (upper)"]
        ), f"Confidence interval of {key} has invalid keys"
        # check the relationship between mean and confidence interval
        assert (
            estimated_intervals[key]["95.0% CI (lower)"] <= estimated_policy_value[key]
        ) and (
            estimated_intervals[key]["95.0% CI (upper)"] >= estimated_policy_value[key]
        ), f"Estimated policy value of {key} is not included in estimated intervals of that estimator"
        assert (
            estimated_intervals[key]["mean"]
            >= estimated_intervals[key]["95.0% CI (lower)"]
        ), f"Invalid confidence interval of {key}: lower bound > mean"
        assert (
            estimated_intervals[key]["mean"]
            <= estimated_intervals[key]["95.0% CI (upper)"]
        ), f"Invalid confidence interval of {key}: upper bound < mean"
