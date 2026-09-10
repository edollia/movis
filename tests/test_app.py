import unittest
from unittest.mock import Mock, patch

import app as app_module


class ProviderTests(unittest.TestCase):
    def test_play_url_builds_movie_and_tv_routes(self):
        self.assertEqual(
            app_module.play_url(1108427),
            "https://67movies.net/watch/movie/1108427",
        )
        self.assertEqual(
            app_module.play_url(1396, "tv", 2, 3),
            "https://67movies.net/watch/tv/1396/2/3",
        )

    def test_play_url_rejects_non_tmdb_ids(self):
        for invalid_id in ("", "0", "tt3521164", "12x"):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaises(ValueError):
                    app_module.play_url(invalid_id)

    def test_cached_results_are_rehydrated_with_typed_urls(self):
        results = app_module.with_play_urls([
            {"id": 1108427, "media_type": "movie", "title": "Moana"},
            {"id": 1396, "media_type": "tv", "title": "Breaking Bad"},
            {"id": "tt3521164", "media_type": "movie", "title": "Old cache entry"},
            {"id": 1, "media_type": "person", "title": "Not a title"},
        ])

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["play_url"], "https://67movies.net/watch/movie/1108427")
        self.assertEqual(results[1]["play_url"], "https://67movies.net/watch/tv/1396/1/1")

    @patch.object(app_module, "remember_search")
    @patch.object(app_module, "cached_search", return_value=None)
    @patch.object(app_module.requests, "get")
    @patch.object(app_module, "TMDB_API_KEY", "test-key")
    def test_search_maps_tmdb_movies_and_tv(self, mock_get, _mock_cache, mock_remember):
        response = Mock()
        response.json.return_value = {
            "results": [
                {
                    "id": 1108427,
                    "media_type": "movie",
                    "title": "Moana",
                    "release_date": "2026-07-08",
                    "poster_path": "/moana.jpg",
                },
                {
                    "id": 1396,
                    "media_type": "tv",
                    "name": "Breaking Bad",
                    "first_air_date": "2008-01-20",
                    "poster_path": "/breaking-bad.jpg",
                },
                {"id": 123, "media_type": "person", "name": "Moana Person"},
            ]
        }
        mock_get.return_value = response

        results = app_module.search_movies("  Moana  ")

        self.assertEqual([result["id"] for result in results], [1108427, 1396])
        self.assertEqual(results[0]["play_url"], "https://67movies.net/watch/movie/1108427")
        self.assertEqual(results[0]["year"], "2026")
        self.assertEqual(results[1]["play_url"], "https://67movies.net/watch/tv/1396/1/1")
        self.assertEqual(results[1]["year"], "2008")
        mock_remember.assert_called_once()

    @patch.object(app_module, "remember_search")
    @patch.object(app_module, "cached_search", return_value=None)
    @patch.object(app_module.requests, "get")
    @patch.object(app_module, "TMDB_API_KEY", "")
    def test_search_uses_filtered_provider_fallback(self, mock_get, _mock_cache, _mock_remember):
        response = Mock()
        response.json.return_value = {
            "results": [
                {"id": 1108427, "media_type": "movie", "title": "Moana"},
                {"id": 1339713, "media_type": "movie", "title": "Obsession"},
            ]
        }
        mock_get.return_value = response

        results = app_module.search_movies("Moana")

        self.assertEqual([result["id"] for result in results], [1108427])
        self.assertEqual(mock_get.call_args.args[0], app_module.SEARCH_FALLBACK_URL)


class RedirectRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_movie_redirect(self):
        response = self.client.get("/play/1108427")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "https://67movies.net/watch/movie/1108427")

    def test_tv_redirects(self):
        expected = "https://67movies.net/watch/tv/1396/2/3"
        response = self.client.get("/watch-tv/1396/2/3")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, expected)

    def test_legacy_imdb_id_is_not_sent_to_67movies(self):
        response = self.client.get("/play/tt3521164")
        self.assertEqual(response.status_code, 404)

    def test_security_headers_are_set(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Referrer-Policy"], "strict-origin-when-cross-origin")


if __name__ == "__main__":
    unittest.main()
