import os
import re
import unittest
from html import unescape
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch

import app as app_module


class ProviderTests(unittest.TestCase):
    def test_upstream_json_has_a_hard_size_limit(self):
        response = app_module.requests.Response()
        response.status_code = 200
        response._content = b"{}"
        response._content_consumed = True
        self.assertEqual(app_module.bounded_response_json(response), {})

        response = app_module.requests.Response()
        response.status_code = 200
        response._content = b"x" * 11
        response._content_consumed = True
        with self.assertRaises(ValueError):
            app_module.bounded_response_json(response, max_bytes=10)

    def test_outbound_configuration_requires_a_safe_http_origin(self):
        unsafe_values = (
            "http://example.com",
            "https://user:password@example.com",
            "https://example.com/watch",
            "javascript:alert(1)",
        )
        for value in unsafe_values:
            with self.subTest(value=value), patch.dict(os.environ, {"TEST_PROVIDER_URL": value}):
                with self.assertRaises(RuntimeError):
                    app_module.configured_http_url(
                        "TEST_PROVIDER_URL",
                        "https://example.com",
                        origin_only=True,
                    )

        with patch.dict(os.environ, {"TEST_PROVIDER_URL": "http://127.0.0.1:8000/"}):
            self.assertEqual(
                app_module.configured_http_url(
                    "TEST_PROVIDER_URL",
                    "https://example.com",
                    origin_only=True,
                ),
                "http://127.0.0.1:8000",
            )

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
        for invalid_id in ("", "0", "tt3521164", "12x", "1" * 11):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaises(ValueError):
                    app_module.play_url(invalid_id)

    def test_play_url_rejects_invalid_media_and_episode_coordinates(self):
        invalid_arguments = (
            {"media_type": "person"},
            {"media_type": "tv", "season": 0, "episode": 1},
            {"media_type": "tv", "season": 1, "episode": 0},
            {"media_type": "tv", "season": 1000, "episode": 1},
            {"media_type": "tv", "season": 1, "episode": 10000},
        )
        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    app_module.play_url(1396, **arguments)

    def test_provider_embed_urls_use_documented_tmdb_routes(self):
        self.assertTrue(app_module.provider_movie_embed_url(27205).startswith(
            "https://player.vidlove.cc/embed/movie/27205?"
        ))
        self.assertTrue(app_module.provider_embed_url(57243, 1, 2).startswith(
            "https://player.vidlove.cc/embed/tv/57243/1/2?"
        ))

    def test_cached_results_are_rehydrated_with_typed_urls(self):
        results = app_module.with_play_urls([
            {"id": 1108427, "media_type": "movie", "title": "Moana"},
            {"id": 1396, "media_type": "tv", "title": "Breaking Bad"},
            {"id": "tt3521164", "media_type": "movie", "title": "Old cache entry"},
            {"id": 1, "media_type": "person", "title": "Not a title"},
        ])

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["play_url"], "/watch-movie/1108427?title=Moana")
        self.assertEqual(results[1]["play_url"], "/watch-tv/1396/1/1?title=Breaking+Bad")

    def test_cached_results_drop_untrusted_metadata_and_urls(self):
        results = app_module.with_play_urls([{
            "id": 1108427,
            "media_type": "movie",
            "title": "Moana\x00<script>",
            "year": {"unexpected": "shape"},
            "poster": "https://attacker.example/tracker.png",
            "play_url": "https://attacker.example/watch",
            "extra": "not exposed",
        }])

        self.assertEqual(results[0]["title"], "Moana <script>")
        self.assertEqual(results[0]["year"], "")
        self.assertEqual(results[0]["poster"], "")
        self.assertNotIn("extra", results[0])
        self.assertEqual(results[0]["play_url"], "/watch-movie/1108427?title=Moana+%3Cscript%3E")

    def test_malformed_cache_entries_are_discarded(self):
        normalized = app_module.normalize_cache({
            "version": app_module.CACHE_SCHEMA_VERSION,
            "entries": {
                "s_valid": {
                    "value": [],
                    "created_at": 1,
                    "last_accessed_at": 2,
                    "expires_at": 3,
                },
                "s_bad_timestamp": {
                    "value": [],
                    "created_at": 1,
                    "last_accessed_at": 2,
                    "expires_at": "never",
                },
                "not_a_search": {
                    "value": [],
                    "created_at": 1,
                    "last_accessed_at": 2,
                    "expires_at": 3,
                },
            },
        })

        self.assertEqual(list(normalized["entries"]), ["s_valid"])

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
        self.assertTrue(results[0]["play_url"].startswith("/watch-movie/1108427?"))
        self.assertIn("title=Moana", results[0]["play_url"])
        self.assertIn("year=2026", results[0]["play_url"])
        self.assertEqual(results[0]["year"], "2026")
        self.assertTrue(results[1]["play_url"].startswith("/watch-tv/1396/1/1?"))
        self.assertIn("title=Breaking+Bad", results[1]["play_url"])
        self.assertIn("year=2008", results[1]["play_url"])
        self.assertEqual(results[1]["year"], "2008")
        mock_remember.assert_called_once()

    @patch.object(app_module, "remember_search")
    @patch.object(app_module, "cached_search", return_value=None)
    @patch.object(app_module.requests, "get")
    @patch.object(app_module, "TMDB_API_KEY", "")
    def test_search_preserves_provider_fallback_breadth(self, mock_get, _mock_cache, _mock_remember):
        response = Mock()
        response.json.return_value = {
            "results": [
                {"id": 1108427, "media_type": "movie", "title": "Moana"},
                {"id": 1339713, "media_type": "movie", "title": "Obsession"},
            ]
        }
        mock_get.return_value = response

        results = app_module.search_movies("Moana")

        self.assertEqual([result["id"] for result in results], [1108427, 1339713])
        self.assertEqual(mock_get.call_args.args[0], app_module.SEARCH_FALLBACK_URL)

    @patch.object(app_module, "remember_search")
    @patch.object(app_module, "cached_search", return_value=None)
    @patch.object(app_module, "fetch_catalog_results")
    def test_search_strips_and_applies_year_like_67movies(
        self,
        mock_fetch,
        _mock_cache,
        _mock_remember,
    ):
        mock_fetch.return_value = [
            {"id": 57243, "media_type": "tv", "name": "Doctor Who", "first_air_date": "2005-03-26"},
            {"id": 121, "media_type": "tv", "name": "Doctor Who", "first_air_date": "1963-11-23"},
        ]

        results = app_module.search_movies("Doctor Who 2005")

        mock_fetch.assert_called_once_with("Doctor Who")
        self.assertEqual([result["id"] for result in results], [57243])

    @patch.object(app_module, "remember_search")
    @patch.object(app_module, "cached_search", return_value=None)
    @patch.object(app_module, "fetch_catalog_results")
    def test_search_normalizes_provider_metadata_and_caps_results(
        self,
        mock_fetch,
        _mock_cache,
        _mock_remember,
    ):
        mock_fetch.return_value = [
            {
                "id": index + 1,
                "media_type": "movie",
                "title": f"Title {index}\x00",
                "release_date": 2026,
                "poster_path": "https://attacker.example/poster.jpg",
            }
            for index in range(app_module.MAX_SEARCH_RESULTS + 10)
        ]

        results = app_module.search_movies("  Doctor\x00\n  Who  ")

        self.assertEqual(len(results), app_module.MAX_SEARCH_RESULTS)
        self.assertEqual(mock_fetch.call_args.args[0], "Doctor Who")
        self.assertEqual(results[0]["title"], "Title 0")
        self.assertEqual(results[0]["year"], "")
        self.assertEqual(results[0]["poster"], "")


class MetadataTests(unittest.TestCase):
    def setUp(self):
        with app_module.metadata_cache_lock:
            app_module.metadata_cache.clear()

    def tearDown(self):
        with app_module.metadata_cache_lock:
            app_module.metadata_cache.clear()

    @patch.object(app_module, "TMDB_API_KEY", "configured-key")
    @patch.object(app_module.requests, "get")
    def test_metadata_uses_proxy_after_tmdb_failure_and_caches_result(self, mock_get):
        response = Mock()
        response.json.return_value = {"name": "Stranger Things", "number_of_seasons": 5}
        mock_get.side_effect = [app_module.requests.RequestException("offline"), response]

        first = app_module.fetch_tmdb_metadata("/3/tv/66732")
        second = app_module.fetch_tmdb_metadata("/3/tv/66732")

        self.assertEqual(first, response.json.return_value)
        self.assertEqual(second, first)
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(mock_get.call_args_list[0].args[0], "https://api.themoviedb.org/3/tv/66732")
        self.assertEqual(mock_get.call_args_list[1].args[0], "https://api.vidlove.cc/tmdb/3/tv/66732")
        response.close.assert_called_once()

    @patch.object(app_module, "fetch_tmdb_metadata")
    def test_tv_metadata_builds_real_seasons_and_named_episodes(self, mock_fetch):
        show = {
            "name": "Stranger Things",
            "first_air_date": "2016-07-15",
            "poster_path": "/poster.jpg",
            "number_of_seasons": 5,
            "seasons": [
                {"season_number": 0, "episode_count": 2},
                {"season_number": 1, "episode_count": 8},
                {"season_number": 2, "episode_count": 9},
            ],
        }
        season = {
            "episodes": [
                {"episode_number": 1, "name": "MADMAX", "air_date": "2017-10-27"},
                {"episode_number": 2, "name": "Trick or Treat, Freak", "air_date": "2017-10-27"},
            ]
        }
        mock_fetch.side_effect = lambda path: season if path.endswith("/season/2") else show

        metadata = app_module.fetch_tv_player_metadata("66732", 2)

        self.assertEqual(metadata["title"], "Stranger Things")
        self.assertEqual(metadata["season_count"], 5)
        self.assertEqual(metadata["season_episode_counts"], {1: 8, 2: 9})
        self.assertEqual(
            [(item["number"], item["name"]) for item in metadata["episodes"]],
            [(1, "MADMAX"), (2, "Trick or Treat, Freak")],
        )


class PlayerRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_movie_entry_route_leads_to_local_player(self):
        response = self.client.get("/play/1108427")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/watch-movie/1108427")

    @patch.object(app_module, "fetch_movie_player_metadata", return_value={})
    def test_movie_renders_local_player_with_direct_provider(self, _mock_metadata):
        response = self.client.get("/watch-movie/27205?title=Inception&year=2010")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("https://player.vidlove.cc/embed/movie/27205?", html)
        self.assertIn("primarycolor=ff4d6d", html)
        self.assertIn("secondarycolor=c49de8", html)
        self.assertIn("server=Archer+Queen", html)
        self.assertIn("hideserver=true", html)
        self.assertIn("autonext=false", html)
        self.assertIn("hidenextbutton=true", html)
        self.assertIn("https://67movies.net/watch/movie/27205", html)
        self.assertIn("data-provider-frame", html)
        self.assertNotIn("sandbox=", html)
        self.assertNotIn("allowfullscreen", html)
        self.assertNotIn("autoplay; fullscreen", html)
        self.assertIn("data-fullscreen-player", html)

    @patch.object(app_module, "fetch_tv_player_metadata", return_value={})
    def test_tv_renders_local_player_with_direct_provider(self, _mock_metadata):
        response = self.client.get("/watch-tv/1396/2/3")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("https://player.vidlove.cc/embed/tv/1396/2/3?", html)
        self.assertIn("server=Archer+Queen", html)
        self.assertIn("hideserver=true", html)
        self.assertIn("autonext=false", html)
        self.assertIn("episodelist=false", html)
        self.assertIn("hideepisodelist=true", html)
        self.assertIn("hidenextbutton=true", html)
        self.assertIn("https://67movies.net/watch/tv/1396/2/3", html)
        self.assertIn("data-provider-frame", html)
        self.assertNotIn("sandbox=", html)
        self.assertNotIn("allowfullscreen", html)
        self.assertNotIn("autoplay; fullscreen", html)
        self.assertIn("data-fullscreen-player", html)

    @patch.object(app_module, "fetch_tv_player_metadata")
    def test_tv_controls_have_real_options_clean_title_and_cross_season_links(self, mock_metadata):
        mock_metadata.return_value = {
            "title": "Stranger Things",
            "year": "2016",
            "poster": "https://image.tmdb.org/t/p/w500/poster.jpg",
            "season_count": 5,
            "season_episode_counts": {1: 8, 2: 9, 3: 8, 4: 9, 5: 8},
            "episodes": [
                {"number": number, "name": f"Chapter {number}", "air_date": ""}
                for number in range(1, 9)
            ],
        }

        response = self.client.get("/watch-tv/66732/1/8")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>Stranger Things S1 E8</title>", html)
        self.assertNotIn("watch-brand", html)
        self.assertNotIn("data-start-over", html)
        self.assertIn("data-fullscreen-player", html)
        self.assertNotIn(">play episode<", html)
        self.assertIn("Reload it.", html)
        self.assertIn(">open here ↗</a>", html)
        self.assertEqual(html.count("<option value=\""), 13)
        self.assertIn("E8 — Chapter 8", html)
        self.assertIn("/watch-tv/66732/1/7?", unescape(html))
        self.assertIn("/watch-tv/66732/2/1?", unescape(html))

        mock_metadata.return_value["episodes"] = [
            {"number": number, "name": f"Chapter {number}", "air_date": ""}
            for number in range(1, 10)
        ]
        response = self.client.get("/watch-tv/66732/2/1")
        self.assertIn("/watch-tv/66732/1/8?", unescape(response.get_data(as_text=True)))

        response = self.client.get("/watch-tv/66732/1/9")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.location).path, "/watch-tv/66732/1/8")

        response = self.client.get("/watch-tv/66732/6/1")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.location).path, "/watch-tv/66732/5/1")

    def test_tv_entry_routes_lead_to_local_player(self):
        response = self.client.get("/tv/1396")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/watch-tv/1396/1/1")

    def test_all_doctor_who_results_keep_type_and_tmdb_id_through_player(self):
        catalog = [
            {
                "id": 57243,
                "media_type": "tv",
                "name": "Doctor Who",
                "first_air_date": "2005-03-26",
                "poster_path": "/m6G92osOtSeXwjSfL21jZCUOvxe.jpg",
                "popularity": 159.282,
            },
            {
                "id": 121,
                "media_type": "tv",
                "name": "Doctor Who",
                "first_air_date": "1963-11-23",
                "poster_path": "/xinqAmYrZ1TEwowcQhgTkZVtVE0.jpg",
                "popularity": 57.1629,
            },
            {
                "id": 239770,
                "media_type": "tv",
                "name": "Doctor Who",
                "first_air_date": "2024-05-11",
                "poster_path": "/2JP6NSmBwxg75uTcIHiv5R8PpPi.jpg",
                "popularity": 27.1417,
            },
            {
                "id": 313106,
                "media_type": "movie",
                "title": "Doctor Who: The Day of the Doctor",
                "release_date": "2013-11-23",
                "poster_path": "/6c0CjymaupC5xerJCemuaSV4CLj.jpg",
                "popularity": 2.4377,
            },
            {
                "id": 282848,
                "media_type": "movie",
                "title": "Doctor Who: The Time of the Doctor",
                "release_date": "2013-12-25",
                "poster_path": "/8GSVpMPlvymndYheKMtQb1aLDBh.jpg",
                "popularity": 1.3685,
            },
        ]
        expected = [
            ("Doctor Who", "2005", "tv", "57243", "/watch-tv/57243/1/1", "/embed/tv/57243/1/1"),
            ("Doctor Who", "1963", "tv", "121", "/watch-tv/121/1/1", "/embed/tv/121/1/1"),
            ("Doctor Who", "2024", "tv", "239770", "/watch-tv/239770/1/1", "/embed/tv/239770/1/1"),
            (
                "Doctor Who: The Day of the Doctor",
                "2013",
                "movie",
                "313106",
                "/watch-movie/313106",
                "/embed/movie/313106",
            ),
            (
                "Doctor Who: The Time of the Doctor",
                "2013",
                "movie",
                "282848",
                "/watch-movie/282848",
                "/embed/movie/282848",
            ),
        ]

        with (
            patch.object(app_module, "cached_search", return_value=None),
            patch.object(app_module, "remember_search"),
            patch.object(app_module, "fetch_catalog_results", return_value=catalog),
        ):
            results = app_module.search_movies("doctor who")
        self.assertEqual(
            [
                (result["title"], result["year"], result["media_type"], str(result["id"]))
                for result in results
            ],
            [(title, year, media_type, tmdb_id) for title, year, media_type, tmdb_id, _, _ in expected],
        )

        with patch.object(app_module, "search_movies", return_value=results):
            response = self.client.get("/search?q=doctor+who")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("arrows browse", response.get_data(as_text=True))
        self.assertNotIn("swipe browses", response.get_data(as_text=True))
        cards = re.findall(
            r'<a class="card-hit" href="([^"]+)" data-card-hit aria-label="Watch ([^"]+)"',
            response.get_data(as_text=True),
        )
        self.assertEqual(len(cards), 5)

        provider_options = {
            "primarycolor": ["ff4d6d"],
            "secondarycolor": ["c49de8"],
            "server": ["Archer Queen"],
            "hideserver": ["true"],
            "autoplay": ["true"],
            "autonext": ["false"],
            "hidenextbutton": ["true"],
            "poster": ["true"],
            "pip": ["true"],
        }
        for (encoded_href, encoded_label), contract in zip(cards, expected):
            title, year, media_type, tmdb_id, local_path, embed_path = contract
            href = unescape(encoded_href)
            label = unescape(encoded_label)
            local_url = urlsplit(href)
            self.assertEqual(label, f"{title}, {year}")
            self.assertEqual(local_url.path, local_path)
            self.assertEqual(parse_qs(local_url.query)["title"], [title])
            self.assertEqual(parse_qs(local_url.query)["year"], [year])

            with (
                patch.object(app_module, "fetch_tv_player_metadata", return_value={}),
                patch.object(app_module, "fetch_movie_player_metadata", return_value={}),
            ):
                player_response = self.client.get(href)
            self.assertEqual(player_response.status_code, 200)
            player_html = player_response.get_data(as_text=True)
            self.assertIn(f'data-media-type="{media_type}"', player_html)
            self.assertIn(f'data-tmdb-id="{tmdb_id}"', player_html)
            frame_match = re.search(
                r'<iframe\s+data-provider-frame\s+src="([^"]+)"',
                player_html,
            )
            self.assertIsNotNone(frame_match)
            frame_url = urlsplit(unescape(frame_match.group(1)))
            self.assertEqual(frame_url.scheme, "https")
            self.assertEqual(frame_url.netloc, "player.vidlove.cc")
            self.assertEqual(frame_url.path, embed_path)
            expected_options = dict(provider_options)
            if media_type == "tv":
                expected_options.update({
                    "episodelist": ["false"],
                    "hideepisodelist": ["true"],
                })
            self.assertEqual(parse_qs(frame_url.query), expected_options)

        response = self.client.get("/play/1396?type=tv")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/watch-tv/1396/1/1")

    def test_tv_redirect_rejects_out_of_range_coordinates(self):
        self.assertEqual(self.client.get("/watch-tv/1396/0/1").status_code, 404)
        self.assertEqual(self.client.get("/watch-tv/1396/1/10000").status_code, 404)

    def test_legacy_imdb_id_is_not_sent_to_67movies(self):
        response = self.client.get("/play/tt3521164")
        self.assertEqual(response.status_code, 404)

    def test_security_headers_are_set(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("fullscreen=(self)", response.headers["Permissions-Policy"])
        self.assertEqual(response.headers["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertIn("object-src 'none'", response.headers["Content-Security-Policy"])
        self.assertNotIn("Strict-Transport-Security", response.headers)

        secure_response = self.client.get("/healthz", base_url="https://goontothis.com")
        self.assertIn("max-age=31536000", secure_response.headers["Strict-Transport-Security"])

    def test_player_csp_allows_only_the_direct_player_frame(self):
        with (
            patch.object(app_module, "fetch_tv_player_metadata", return_value={}),
            patch.object(app_module, "fetch_movie_player_metadata", return_value={}),
        ):
            player_response = self.client.get("/watch-tv/1396/1/1")
            movie_csp = self.client.get("/watch-movie/27205").headers["Content-Security-Policy"]
        player_csp = player_response.headers["Content-Security-Policy"]
        self.assertIn("frame-src https://player.vidlove.cc", player_csp)
        self.assertNotIn("frame-src 'none'", player_csp)

        self.assertIn("frame-src https://player.vidlove.cc", movie_csp)

        normal_csp = self.client.get("/").headers["Content-Security-Policy"]
        self.assertIn("frame-src 'none'", normal_csp)
        self.assertNotIn("player.vidlove.cc", normal_csp)

    def test_inline_scripts_use_the_per_request_csp_nonce(self):
        response = self.client.get("/")
        csp = response.headers["Content-Security-Policy"]
        nonce_match = re.search(r"'nonce-([^']+)'", csp)

        self.assertIsNotNone(nonce_match)
        nonce = nonce_match.group(1)
        html = response.get_data(as_text=True)
        self.assertIn(f'nonce="{nonce}"', html)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", csp)


if __name__ == "__main__":
    unittest.main()
