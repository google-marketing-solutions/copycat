# Copyright 2024 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Organises keywords into semantically similar ad groups."""

import abc
import logging
import numpy as np
from sklearn import cluster
from sklearn import metrics
import tqdm

ARBITRARILY_HIGH_DISTANCE_THRESHOLD = 10.0

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class TqdmLogger:
  """File-like class redirecting tqdm progress bar to LOGGER."""

  def write(self, msg: str) -> None:
    LOGGER.info(msg.lstrip("\r"))

  def flush(self) -> None:
    pass


class KeywordClusterer(abc.ABC):
  """Abstract class for clustering keywords.

  Attributes:
    distance_threshold: The distance threshold to use for clustering - keywords
      with a distance less than this will be considered to be in the same ad
      group. This is initialized to None and then learned when fit is called.
    max_training_samples: The maximum number of samples to use for training. If
      more samples are provided, then a random subset of the samples will be
      used.
  """

  distance_threshold: float | None
  max_training_samples: int

  def __init__(self, max_training_samples: int = 5000):
    """Initialises the keyword clusterer.

    Args:
      max_training_samples: The maximum number of samples to use for training.
        If more samples are provided, then a random subset of the samples will
        be used.
    """
    self.distance_threshold = None
    self.max_training_samples = max_training_samples

  @abc.abstractmethod
  def _fit(
      self, keyword_embeddings: np.ndarray, target_ad_groups: np.ndarray
  ) -> None:
    """Fits the clusterer to the given keyword embeddings and target ad groups.

    This should learn the distance threshold such that the predicted ad groups
    produced are as similar as possible to the target ad groups. This method
    should be implemented by subclasses.

    Args:
      keyword_embeddings: The text embeddings of the keywords as a numpy array.
      target_ad_groups: The target as groups as an array of integers.
    """
    ...

  def fit(
      self, keyword_embeddings: np.ndarray, target_ad_groups: np.ndarray
  ) -> None:
    """Fits the clusterer to the given keyword embeddings and target ad groups.

    This will learn the distance threshold such that the predicted ad groups
    produced are as similar as possible to the target ad groups. It first
    downsamples the data to max_training_samples if necessary, before fitting.

    Args:
      keyword_embeddings: The text embeddings of the keywords as a numpy array.
      target_ad_groups: The target as groups as an array of integers.
    """
    if len(target_ad_groups) > self.max_training_samples:
      idx = np.random.choice(
          len(target_ad_groups), self.max_training_samples, replace=False
      )
      keyword_embeddings = keyword_embeddings[idx, :]
      target_ad_groups = target_ad_groups[idx]

    self._fit(keyword_embeddings, target_ad_groups)

  @abc.abstractmethod
  def predict(self, keyword_embeddings: np.ndarray) -> np.ndarray:
    """Predicts the ad groups for the given keyword embeddings.

    Args:
      keyword_embeddings: The keyword embeddings to use for clustering.

    Returns:
      The predicted ad group clusters as an array of integers.
    """
    ...

  def _evaluate_targets(
      self, target_ad_groups: np.ndarray, predicted_ad_groups: np.ndarray
  ) -> float:
    """Evaluates the predicted ad groups against the target ad groups.

    Args:
      target_ad_groups: The target ad groups as an array of integers.
      predicted_ad_groups: The predicted ad groups as an array of integers.

    Returns:
      The adjusted rand score between the target and predicted ad groups.
    """
    return metrics.adjusted_rand_score(target_ad_groups, predicted_ad_groups)

  def evaluate(
      self, keyword_embeddings: np.ndarray, target_ad_groups: np.ndarray
  ) -> float:
    """First clusters the provided keyword embeddings and then evaluates.

    The predicted ad groups are evaluated against the target ad groups using
    the adjusted rand score.

    Args:
      keyword_embeddings: The keyword embeddings to use for clustering.
      target_ad_groups: The target ad groups as an array of integers.

    Returns:
      The adjusted rand score between the target and predicted ad groups.
    """
    predicted_ad_groups = self.predict(keyword_embeddings)
    return self._evaluate_targets(target_ad_groups, predicted_ad_groups)


class BirchAgglomerativeKeywordClusterer(KeywordClusterer):
  """Clusters keywords using BIRCH and agglomerative clustering.

  This first learns the optimal distance threshold for agglomerative clustering
  at the fit step.

  When predicting, BIRCH clustering is performed first to improve the
  scalability of the clustering. BIRCH uses a threshold which is the learned
  distance threshold, multiplied by the birch_scale. This scaling controls how
  much of the clustering is performed by BIRCH and how much is performed by
  agglomerative clustering. If birch_scale is set to 0, then only
  agglomerative clustering is performed, if it is set to 1 then almost all of
  the clustering will be performed by BIRCH. A higher birch scale
  leads to a more scalable algorithm but usually worse performance.

  Attributes:
    birch_scale: The scale to use for BIRCH. This is a value between 0 and 1
      that controls how much BIRCH contributes to the clustering. A high value
      means BIRCH contributes more, and will be more scalable but less accurate.
  """

  def __init__(
      self, birch_scale: float = 0.5, max_training_samples: int = 5000
  ):
    """Initialises the keyword clusterer.

    Args:
      birch_scale: The scale to use for BIRCH. This is a value between 0 and 1
        that controls how much BIRCH contributes to the clustering. A high value
        means BIRCH contributes more, and will be more scalable but less
        accurate.
      max_training_samples: The maximum number of samples to use for training.
        If more samples are provided, then a random subset of the samples will
        be used.
    """
    super().__init__(max_training_samples=max_training_samples)
    self.birch_scale = birch_scale
    if self.birch_scale >= 1.0 or self.birch_scale < 0.0:
      LOGGER.error(
          "Birch scale must be >=0 and <1, but got %f", self.birch_scale
      )
      raise ValueError(
          f"Birch scale must be >=0 and <1, but got {self.birch_scale}"
      )

  def _fit(
      self, keyword_embeddings: np.ndarray, target_ad_groups: np.ndarray
  ) -> None:
    """Fits the clusterer to the given keyword embeddings and target ad groups.

    This will learn the distance threshold such that the predicted ad groups
    produced are as similar as possible to the target ad groups. It does this
    by applying Agglomerative Clustering across a variety of distance thresholds
    and then selecting the threshold that produces the highest adjusted rand
    score when comparing the predicted ad groups to the target ad groups.

    Args:
      keyword_embeddings: The text embeddings of the keywords as a numpy array.
      target_ad_groups: The target as groups as an array of integers.
    """
    LOGGER.info(
        "Fitting the distance threshold of BirchAgglomerativeKeywordClusterer."
    )

    # Construct the tree using AgglomerativeClustering with a high distance
    # threshold. This tree tells you the order in which the keywords are merged,
    # starting with the most similar and continuing recursively until they are
    # all merged into a single cluster. We will use this tree to find the
    # optimal distance threshold.
    clustering = cluster.AgglomerativeClustering(
        n_clusters=None,
        linkage="average",
        distance_threshold=ARBITRARILY_HIGH_DISTANCE_THRESHOLD,
        compute_distances=True,
        compute_full_tree=True,
    )
    clustering.fit(keyword_embeddings)

    LOGGER.info("Finished constructing the tree with AgglomerativeClustering.")

    # Iterate through the tree, calculating the rand score at each step in the
    # clustering.
    clusters = [[i] for i in range(len(target_ad_groups))]
    predicted_ad_groups = np.arange(len(target_ad_groups))
    next_cluster_id = len(target_ad_groups)

    distance = clustering.distances_
    rand_score = []

    for i, j in tqdm.tqdm(
        clustering.children_,
        desc="Fitting distance threshold",
        file=TqdmLogger(),
        mininterval=5,
    ):
      new_cluster = clusters[i] + clusters[j]

      for k in new_cluster:
        predicted_ad_groups[k] = next_cluster_id

      clusters.append(new_cluster)
      next_cluster_id += 1

      rand_score.append(
          self._evaluate_targets(target_ad_groups, predicted_ad_groups)
      )

    # The best distance is the distance with the highest score
    distance = np.asarray(distance)
    rand_score = np.asarray(rand_score)
    self.distance_threshold = distance[np.argmax(rand_score)]
    LOGGER.info(
        "Found the optimal distance threshold: %f with rand score: %f",
        self.distance_threshold,
        np.max(rand_score),
    )

  def predict(self, keyword_embeddings: np.ndarray) -> np.ndarray:
    """Predicts the ad groups for the given keyword embeddings.

    This will first perform BIRCH clustering to produce a set of initial
    clusters, and then perform agglomerative clustering to produce the final
    clusters. If birch_scale is set to 0, then no BIRCH clustering will be
    performed.

    Args:
      keyword_embeddings: The keyword embeddings to use for clustering.

    Returns:
      The predicted ad group clusters as an array of integers.

    Raises:
      ValueError: If the distance threshold has not been learned yet (meaning
        fit() has not been called).
    """
    LOGGER.info("Predicting ad groups with BirchAgglomerativeKeywordClusterer.")
    if self.distance_threshold is None:
      LOGGER.error("Must call fit before predicting ad groups.")
      raise ValueError("Must call fit before predicting ad groups.")

    agglomerative_clustering = cluster.AgglomerativeClustering(
        n_clusters=None,
        linkage="average",
        distance_threshold=self.distance_threshold,
    )
    if self.birch_scale > 0.0:
      LOGGER.info(
          "Performing BIRCH clustering with scale: %f", self.birch_scale
      )
      clustering = cluster.Birch(
          threshold=self.distance_threshold * self.birch_scale,
          n_clusters=agglomerative_clustering,
      )
    else:
      LOGGER.info("Skipping BIRCH clustering because birch scale is 0.")
      clustering = agglomerative_clustering
    return clustering.fit_predict(keyword_embeddings)
