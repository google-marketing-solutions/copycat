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

from absl.testing import absltest
from absl.testing import parameterized
import mock
import numpy as np
from sklearn import cluster

from copycat import keyword_organiser


class KeywordOrganiserTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.train_keyword_embeddings = np.array([
        [0.5, 0.7, 1.0],
        [0.2, 0.9, 3.0],
        [-1.0, -2.0, -1.0],
        [-1.0, -5.0, -2.0],
    ])
    self.train_target_ad_groups = np.array([1, 1, 0, 0])
    self.test_keyword_embeddings = np.array([
        [-0.5, 0.2, 2.0],
        [0.3, 0.1, -3.5],
        [-1.0, 2.0, -1.0],
    ])

  def test_fit_learns_the_distance_threshold(self):
    clusterer = keyword_organiser.BirchAgglomerativeKeywordClusterer()
    clusterer.fit(
        keyword_embeddings=self.train_keyword_embeddings,
        target_ad_groups=self.train_target_ad_groups,
    )
    self.assertAlmostEqual(clusterer.distance_threshold, 3.1622776601683795)

  def test_predict_raises_error_if_not_fit(self):
    clusterer = keyword_organiser.BirchAgglomerativeKeywordClusterer()
    with self.assertRaisesWithLiteralMatch(
        ValueError, "Must call fit before predicting ad groups."
    ):
      clusterer.predict(self.test_keyword_embeddings)

  def test_predict_returns_expected_clusters(self):
    clusterer = keyword_organiser.BirchAgglomerativeKeywordClusterer()
    clusterer.fit(
        keyword_embeddings=self.train_keyword_embeddings,
        target_ad_groups=self.train_target_ad_groups,
    )
    predicted_ad_groups = clusterer.predict(self.test_keyword_embeddings)
    np.testing.assert_array_equal(predicted_ad_groups, np.array([1, 2, 0]))

  def test_evaluate_returns_expected_score(self):
    clusterer = keyword_organiser.BirchAgglomerativeKeywordClusterer()
    clusterer.fit(
        keyword_embeddings=self.train_keyword_embeddings,
        target_ad_groups=self.train_target_ad_groups,
    )
    score = clusterer.evaluate(
        keyword_embeddings=self.train_keyword_embeddings,
        target_ad_groups=self.train_target_ad_groups,
    )
    self.assertAlmostEqual(score, 1.0)

  def test_fit_calls_agglomerative_clustering_with_expected_args(
      self,
  ):
    clusterer = keyword_organiser.BirchAgglomerativeKeywordClusterer()
    with mock.patch(
        "sklearn.cluster.AgglomerativeClustering"
    ) as mock_agglomerative_clustering:
      mock_agglomerative_clustering.return_value.distances_ = np.array([
          1.0,
          2.0,
          3.0,
          4.0,
      ])
      mock_agglomerative_clustering.return_value.children_ = [
          (0, 1),
          (2, 3),
      ]

      clusterer.fit(
          keyword_embeddings=self.train_keyword_embeddings,
          target_ad_groups=self.train_target_ad_groups,
      )
      mock_agglomerative_clustering.assert_called_once_with(
          n_clusters=None,
          linkage="average",
          distance_threshold=10.0,
          compute_distances=True,
          compute_full_tree=True,
      )

  def test_predict_calls_agglomerative_clustering_with_expected_args(
      self,
  ):
    clusterer = keyword_organiser.BirchAgglomerativeKeywordClusterer()
    clusterer.fit(
        keyword_embeddings=self.train_keyword_embeddings,
        target_ad_groups=self.train_target_ad_groups,
    )
    with mock.patch(
        "sklearn.cluster.AgglomerativeClustering",
    ) as mock_agglomerative_clustering:
      clusterer.predict(self.test_keyword_embeddings)
      mock_agglomerative_clustering.assert_called_once_with(
          n_clusters=None,
          linkage="average",
          distance_threshold=clusterer.distance_threshold,
      )

  def test_birch_used_if_scale_is_greater_than_zero(self):
    clusterer = keyword_organiser.BirchAgglomerativeKeywordClusterer(
        birch_scale=0.5
    )
    clusterer.fit(
        keyword_embeddings=self.train_keyword_embeddings,
        target_ad_groups=self.train_target_ad_groups,
    )
    with mock.patch(
        "sklearn.cluster.Birch",
    ) as mock_birch:
      with mock.patch(
          "sklearn.cluster.AgglomerativeClustering",
      ) as mock_agglomerative_clustering:
        predicted_ad_groups = clusterer.predict(self.test_keyword_embeddings)

        # Test birch is instantiated with the expected arguments
        mock_agglomerative_clustering_instance = (
            mock_agglomerative_clustering.return_value
        )
        mock_birch.assert_called_once_with(
            threshold=clusterer.distance_threshold * clusterer.birch_scale,
            n_clusters=mock_agglomerative_clustering_instance,
        )

        # Test birch fit_predict is called with the expected arguments
        mock_birch_instance = mock_birch.return_value
        mock_birch_instance.fit_predict.assert_called_once_with(
            self.test_keyword_embeddings
        )

        # Test fit predict returns the output from fit predict
        self.assertIs(
            predicted_ad_groups, mock_birch_instance.fit_predict.return_value
        )

  def test_birch_not_used_if_scale_is_zero(self):
    clusterer = keyword_organiser.BirchAgglomerativeKeywordClusterer(
        birch_scale=0.0
    )
    clusterer.fit(
        keyword_embeddings=self.train_keyword_embeddings,
        target_ad_groups=self.train_target_ad_groups,
    )
    with mock.patch(
        "sklearn.cluster.Birch",
    ) as mock_birch:
      with mock.patch(
          "sklearn.cluster.AgglomerativeClustering",
      ) as mock_agglomerative_clustering:
        predicted_ad_groups = clusterer.predict(self.test_keyword_embeddings)

        # Test birch is not called
        mock_birch.assert_not_called()

        # Test agglomerative fit_predict is called with the expected arguments
        mock_agglomerative_clustering_instance = (
            mock_agglomerative_clustering.return_value
        )
        mock_agglomerative_clustering_instance.fit_predict.assert_called_once_with(
            self.test_keyword_embeddings
        )

        # Test fit predict returns the output from fit predict
        self.assertIs(
            predicted_ad_groups,
            mock_agglomerative_clustering_instance.fit_predict.return_value,
        )

  @parameterized.parameters([
      1.0,
      -0.1,
  ])
  def test_value_error_raised_if_birch_scale_is_invalid(self, birch_scale):
    with self.assertRaisesWithLiteralMatch(
        ValueError, f"Birch scale must be >=0 and <1, but got {birch_scale}"
    ):
      keyword_organiser.BirchAgglomerativeKeywordClusterer(
          birch_scale=birch_scale
      )


if __name__ == "__main__":
  absltest.main()
