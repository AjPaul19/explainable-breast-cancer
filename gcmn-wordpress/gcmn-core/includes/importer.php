<?php
defined( 'ABSPATH' ) || exit;

/**
 * Content import. Loads the approved content from a JSON file, so the site goes live with real content and nothing is typed in by hand.
 * Run it with WP-CLI:   wp gcmn import content/gcmn-content.json --media=content/media
 * Running it again updates the same items (matched by "key"), so it is safe to repeat.
 *
 * File shape (every part optional):
 * {
 *   "settings": { "tagline": "...", "email": "..." },                       // any key from Settings > GCMN site
 *   "pages":    [ { "slug": "who-we-are", "title": "...", "content": "<p>..</p>", "parent": "", "order": 10 } ],
 *   "items":    [ { "type": "gcmn_strategy", "slug": "...", "title": "...", "content": "<p>..</p>", "excerpt": "...",
 *                   "date": "2026-03-01", "image": "file-in-media-dir.jpg", "strategy": "slug-of-strategy",
 *                   "categories": ["News"], "dept": "Department", "meta": { "locations": "..." } } ],
 *   "menus":    { "primary": [ { "title": "Who we are", "page": "who-we-are" } ], "footer": [ ... ] }
 * }
 */
function gcmn_import_file( $file, $media_dir = '', $force = false ) {
	if ( ! is_readable( $file ) ) {
		return new WP_Error( 'gcmn_import', 'Cannot read ' . $file );
	}
	$data = json_decode( (string) file_get_contents( $file ), true );
	if ( ! is_array( $data ) ) {
		return new WP_Error( 'gcmn_import', 'The file is not valid JSON.' );
	}
	return gcmn_import_data( $data, $media_dir, $force );
}

function gcmn_import_find( $key ) {
	$found = get_posts( array(
		'post_type' => 'any', 'post_status' => 'any', 'numberposts' => 1, 'fields' => 'ids',
		'meta_query' => array( array( 'key' => '_gcmn_import_key', 'value' => $key ) ),
	) );
	return $found ? (int) $found[0] : 0;
}

function gcmn_import_media( $name, $media_dir, $post_id ) {
	if ( ! $name || ! $media_dir ) {
		return 0;
	}
	$path = realpath( trailingslashit( $media_dir ) . $name );
	$root = realpath( $media_dir );
	if ( ! $path || ! $root || 0 !== strpos( $path, $root ) || ! is_file( $path ) ) {
		return 0; // never read outside the media folder
	}
	require_once ABSPATH . 'wp-admin/includes/image.php';
	require_once ABSPATH . 'wp-admin/includes/file.php';
	$existing = get_posts( array( 'post_type' => 'attachment', 'post_status' => 'inherit', 'numberposts' => 1, 'fields' => 'ids', 'meta_query' => array( array( 'key' => '_gcmn_import_media', 'value' => $name ) ) ) );
	if ( $existing ) {
		return (int) $existing[0];
	}
	$type = wp_check_filetype( basename( $path ) );
	if ( empty( $type['type'] ) ) {
		return 0;
	}
	$bits = wp_upload_bits( basename( $path ), null, (string) file_get_contents( $path ) );
	if ( ! empty( $bits['error'] ) ) {
		return 0;
	}
	$att = wp_insert_attachment( array(
		'post_mime_type' => $type['type'],
		'post_title'     => sanitize_text_field( pathinfo( $path, PATHINFO_FILENAME ) ),
		'post_status'    => 'inherit',
	), $bits['file'], $post_id );
	if ( is_wp_error( $att ) || ! $att ) {
		return 0;
	}
	wp_update_attachment_metadata( $att, wp_generate_attachment_metadata( $att, $bits['file'] ) );
	update_post_meta( $att, '_gcmn_import_media', $name );
	return (int) $att;
}

/**
 * The importer works in small, repeatable steps so a slow host never leaves the site half built:
 * settings, pages, items, page layouts, menus, then the header and footer. Each step can be run again safely.
 *
 * $force false (the default): anything imported before is left exactly as it is, so edits made in Elementor are never overwritten.
 *   A page that was imported before layouts existed (it has no layout yet) is brought up to date.
 * $force true: reset imported pages, items, menus, settings and the header and footer to the content file.
 */
function gcmn_import_sorted( array $data ) {
	$pages = (array) ( isset( $data['pages'] ) ? $data['pages'] : array() );
	usort( $pages, function ( $a, $b ) {
		$da = substr_count( isset( $a['path'] ) ? $a['path'] : ( isset( $a['slug'] ) ? $a['slug'] : '' ), '/' );
		$db = substr_count( isset( $b['path'] ) ? $b['path'] : ( isset( $b['slug'] ) ? $b['slug'] : '' ), '/' );
		return $da <=> $db;
	} );
	$items = (array) ( isset( $data['items'] ) ? $data['items'] : array() );
	usort( $items, function ( $a, $b ) { // strategies first so other items can point to them
		return ( ( isset( $a['type'] ) ? $a['type'] : '' ) === 'gcmn_strategy' ? 0 : 1 ) <=> ( ( isset( $b['type'] ) ? $b['type'] : '' ) === 'gcmn_strategy' ? 0 : 1 );
	} );
	return array( $pages, $items );
}

function gcmn_import_settings( array $data, $force ) {
	if ( ! empty( $data['site_title'] ) && ( $force || 'My WordPress Website' === get_option( 'blogname' ) || ! get_option( 'blogname' ) || false !== stripos( get_option( 'blogname' ), 'wordpress' ) ) ) {
		try {
			update_option( 'blogname', sanitize_text_field( $data['site_title'] ) );
		} catch ( Exception $e ) { // phpcs:ignore Generic.CodeAnalysis.EmptyStatement.DetectedCatch -- Elementor's site-name sync is not needed for the import
		}
	}
	if ( ! empty( $data['site_description'] ) && ( $force || ! get_option( 'blogdescription' ) || 'Just another WordPress site' === get_option( 'blogdescription' ) ) ) {
		update_option( 'blogdescription', sanitize_text_field( $data['site_description'] ) );
	}
	if ( ! empty( $data['settings'] ) && is_array( $data['settings'] ) ) {
		$current = get_option( 'gcmn_settings', array() );
		$current = is_array( $current ) ? $current : array();
		update_option( 'gcmn_settings', gcmn_sanitize_settings( $force ? array_merge( $current, $data['settings'] ) : array_merge( $data['settings'], array_filter( $current, 'strlen' ) ) ) );
	}
}

/** One page. Returns 1 if it was created or updated. */
function gcmn_import_page( array $p, $media_dir, $force, array &$report ) {
	if ( empty( $p['slug'] ) || empty( $p['title'] ) ) {
		$report['skipped'][] = 'page without slug or title';
		return 0;
	}
	$path  = isset( $p['path'] ) ? $p['path'] : $p['slug'];
	$key   = 'page:' . $path;
	$found = gcmn_import_find( $key );
	if ( $found && ! $force && ( empty( $p['layout'] ) || get_post_meta( $found, '_gcmn_layout', true ) ) ) {
		return 0; // imported before and built: leave it as the editor left it
	}
	$id     = $found ?: ( ( $x = get_page_by_path( $path ) ) ? (int) $x->ID : 0 );
	$parent = ! empty( $p['parent'] ) && ( $pp = get_page_by_path( $p['parent'] ) ) ? (int) $pp->ID : 0;
	$args   = array(
		'ID'           => $id,
		'post_type'    => 'page',
		'post_status'  => 'publish',
		'post_title'   => sanitize_text_field( $p['title'] ),
		'post_name'    => sanitize_title( $p['slug'] ),
		'post_content' => wp_kses_post( isset( $p['content'] ) ? $p['content'] : '' ),
		'post_excerpt' => sanitize_text_field( isset( $p['excerpt'] ) ? $p['excerpt'] : '' ),
		'post_parent'  => $parent,
		'menu_order'   => isset( $p['order'] ) ? (int) $p['order'] : 0,
	);
	$id = $id ? wp_update_post( $args, true ) : wp_insert_post( $args, true );
	if ( is_wp_error( $id ) ) {
		$report['skipped'][] = $p['slug'] . ': ' . $id->get_error_message();
		return 0;
	}
	update_post_meta( $id, '_gcmn_import_key', $key );
	update_post_meta( $id, '_gcmn_qc', '1' );
	update_post_meta( $id, '_gcmn_approved', '1' );
	update_post_meta( $id, '_gcmn_approver', 'Imported from the previous website' );
	if ( ! empty( $p['dept'] ) ) {
		update_post_meta( $id, '_gcmn_dept', sanitize_text_field( $p['dept'] ) );
	}
	update_post_meta( $id, '_gcmn_review', gmdate( 'Y-m-d', strtotime( '+' . gcmn_default_review_days( 'page' ) . ' days' ) ) );
	if ( ! empty( $p['layout'] ) ) {
		update_post_meta( $id, '_gcmn_layout_pending', '1' ); // built in the layouts step, when every page it links to exists
	}
	if ( ! empty( $p['image'] ) && ( $att = gcmn_import_media( $p['image'], $media_dir, $id ) ) ) {
		set_post_thumbnail( $id, $att );
	}
	return 1;
}

/** One item (strategy, story, resource, news ...). Returns 1 if it was created or updated. */
function gcmn_import_item( array $it, $media_dir, $force, array &$report ) {
	static $allowed = array( 'post', 'gcmn_strategy', 'gcmn_story', 'gcmn_event', 'gcmn_resource', 'gcmn_prayer', 'gcmn_opportunity' );
	$type = isset( $it['type'] ) ? $it['type'] : '';
	if ( ! in_array( $type, $allowed, true ) || empty( $it['slug'] ) || empty( $it['title'] ) ) {
		$report['skipped'][] = 'item without a valid type, slug or title';
		return 0;
	}
	$key = $type . ':' . $it['slug'];
	$id  = gcmn_import_find( $key );
	if ( $id && ! $force ) {
		return 0;
	}
	$args = array(
		'ID'           => $id,
		'post_type'    => $type,
		'post_status'  => 'publish',
		'post_title'   => sanitize_text_field( $it['title'] ),
		'post_name'    => sanitize_title( $it['slug'] ),
		'post_content' => wp_kses_post( isset( $it['content'] ) ? $it['content'] : '' ),
		'post_excerpt' => sanitize_text_field( isset( $it['excerpt'] ) ? $it['excerpt'] : '' ),
	);
	if ( ! empty( $it['date'] ) && strtotime( $it['date'] ) ) {
		$args['post_date'] = gmdate( 'Y-m-d H:i:s', strtotime( $it['date'] ) );
	}
	$id = $id ? wp_update_post( $args, true ) : wp_insert_post( $args, true );
	if ( is_wp_error( $id ) ) {
		$report['skipped'][] = $it['slug'] . ': ' . $id->get_error_message();
		return 0;
	}
	update_post_meta( $id, '_gcmn_import_key', $key );
	update_post_meta( $id, '_gcmn_qc', '1' );
	update_post_meta( $id, '_gcmn_approved', '1' );
	update_post_meta( $id, '_gcmn_approver', 'Imported from the previous website' );
	update_post_meta( $id, '_gcmn_review', gmdate( 'Y-m-d', strtotime( '+' . gcmn_default_review_days( $type ) . ' days' ) ) );
	if ( false !== strpos( $args['post_content'], '[[img:' ) ) {
		wp_update_post( array( 'ID' => $id, 'post_content' => gcmn_import_tokens( get_post_field( 'post_content', $id ), $media_dir, $id ) ) );
	}
	if ( ! empty( $it['dept'] ) ) {
		update_post_meta( $id, '_gcmn_dept', sanitize_text_field( $it['dept'] ) );
	}
	if ( ! empty( $it['strategy'] ) && ( $sid = gcmn_import_find( 'gcmn_strategy:' . $it['strategy'] ) ) ) {
		update_post_meta( $id, '_gcmn_strategy', $sid );
	}
	$fields = gcmn_detail_fields( $type );
	foreach ( (array) ( isset( $it['meta'] ) ? $it['meta'] : array() ) as $k => $v ) {
		if ( isset( $fields[ $k ] ) && 'strategy' !== $k ) {
			$f = $fields[ $k ][0];
			update_post_meta( $id, '_gcmn_' . $k, in_array( $f, array( 'url', 'media' ), true ) ? esc_url_raw( $v ) : sanitize_text_field( $v ) );
		}
	}
	if ( 'gcmn_story' === $type ) {
		update_post_meta( $id, '_gcmn_consent', '1' ); // Imported stories were already published on the old site.
	}
	if ( 'post' === $type && ! empty( $it['categories'] ) ) {
		$ids = array();
		foreach ( (array) $it['categories'] as $c ) {
			$t = term_exists( $c, 'category' ) ?: wp_insert_term( $c, 'category' );
			if ( ! is_wp_error( $t ) ) {
				$ids[] = (int) ( is_array( $t ) ? $t['term_id'] : $t );
			}
		}
		wp_set_post_categories( $id, $ids );
	}
	if ( ! empty( $it['image'] ) && ( $att = gcmn_import_media( $it['image'], $media_dir, $id ) ) ) {
		set_post_thumbnail( $id, $att );
	}
	return 1;
}

function gcmn_import_menus( array $data, $force ) {
	$made = 0;
	foreach ( (array) ( isset( $data['menus'] ) ? $data['menus'] : array() ) as $location => $entries ) {
		if ( ! in_array( $location, array( 'primary', 'footer' ), true ) ) {
			continue;
		}
		$menu = wp_get_nav_menu_object( 'GCMN ' . $location );
		if ( $menu && ! $force && wp_get_nav_menu_items( $menu->term_id ) ) {
			continue; // the menu already exists and may have been edited
		}
		$menu_id = $menu ? (int) $menu->term_id : (int) wp_create_nav_menu( 'GCMN ' . $location );
		foreach ( (array) wp_get_nav_menu_items( $menu_id ) as $old ) {
			wp_delete_post( $old->ID, true );
		}
		$add = null;
		$add = function ( $entries, $parent ) use ( &$add, $menu_id ) {
			foreach ( (array) $entries as $n => $e ) {
				$item = array( 'menu-item-title' => sanitize_text_field( isset( $e['title'] ) ? $e['title'] : '' ), 'menu-item-status' => 'publish', 'menu-item-position' => $n + 1, 'menu-item-parent-id' => $parent );
				if ( ! empty( $e['class'] ) ) {
					$item['menu-item-classes'] = sanitize_html_class( $e['class'] );
				}
				if ( ! empty( $e['page'] ) && ( $pg = gcmn_page_by_slug( $e['page'] ) ) ) {
					$item += array( 'menu-item-type' => 'post_type', 'menu-item-object' => 'page', 'menu-item-object-id' => $pg->ID );
				} elseif ( ! empty( $e['item'] ) && ( $iid = gcmn_import_find( $e['item'] ) ) ) {
					$item += array( 'menu-item-type' => 'post_type', 'menu-item-object' => get_post_type( $iid ), 'menu-item-object-id' => $iid );
				} elseif ( ! empty( $e['archive'] ) && post_type_exists( $e['archive'] ) ) {
					$item += array( 'menu-item-type' => 'post_type_archive', 'menu-item-object' => $e['archive'] );
				} elseif ( ! empty( $e['url'] ) ) {
					$item += array( 'menu-item-type' => 'custom', 'menu-item-url' => esc_url_raw( $e['url'] ) );
				} else {
					continue;
				}
				$mid = wp_update_nav_menu_item( $menu_id, 0, $item );
				if ( ! empty( $e['children'] ) && ! is_wp_error( $mid ) ) {
					$add( $e['children'], (int) $mid );
				}
			}
		};
		$add( $entries, 0 );
		$saved = get_option( 'gcmn_menu_ids', array() );
		$saved[ $location ] = $menu_id;
		update_option( 'gcmn_menu_ids', $saved );
		$locs = get_theme_mod( 'nav_menu_locations', array() );
		$locs[ $location ] = $menu_id;
		set_theme_mod( 'nav_menu_locations', $locs );
		$made++;
	}
	return $made;
}

/** The ID of a page that still needs its layout built, or 0. */
function gcmn_import_next_layout() {
	$f = get_posts( array( 'post_type' => 'page', 'post_status' => 'any', 'numberposts' => 1, 'fields' => 'ids', 'meta_key' => '_gcmn_layout_pending', 'meta_value' => '1' ) );
	return $f ? (int) $f[0] : 0;
}

function gcmn_import_pending_count() {
	$q = new WP_Query( array( 'post_type' => 'page', 'post_status' => 'any', 'posts_per_page' => 1, 'fields' => 'ids', 'meta_key' => '_gcmn_layout_pending', 'meta_value' => '1', 'no_found_rows' => false ) );
	return (int) $q->found_posts;
}

/**
 * Run the import for up to $limit units of work (one page, one item or one layout is one unit; 0 means no limit).
 * $state: array( 'phase' => settings|pages|items|layouts|menus|finish|done, 'offset' => int, 'counts' => array ).
 * Returns array( 'state' => ..., 'done' => bool, 'percent' => int, 'report' => array ).
 */
function gcmn_import_run( array $data, $media_dir = '', $force = false, $state = null, $limit = 0 ) {
	if ( ! defined( 'GCMN_IMPORTING' ) ) {
		define( 'GCMN_IMPORTING', true );
	}
	if ( function_exists( 'set_time_limit' ) ) {
		@set_time_limit( 0 ); // phpcs:ignore WordPress.PHP.NoSilencedErrors.Discouraged
	}
	if ( ! get_current_user_id() ) { // WP-CLI, cron and tests run with no user; Elementor refuses site-name changes then
		$admins = get_users( array( 'role' => 'administrator', 'number' => 1, 'fields' => 'ID' ) );
		if ( $admins ) {
			wp_set_current_user( (int) $admins[0] );
		}
	}
	gcmn_register_content_types();
	if ( ! is_array( $state ) || empty( $state['phase'] ) ) {
		$state = array( 'phase' => 'settings', 'offset' => 0, 'counts' => array( 'pages' => 0, 'items' => 0, 'menus' => 0 ) );
	}
	$report = array( 'skipped' => array() );
	list( $pages, $items ) = gcmn_import_sorted( $data );
	$by_path = array();
	foreach ( $pages as $p ) {
		$by_path[ 'page:' . ( isset( $p['path'] ) ? $p['path'] : ( isset( $p['slug'] ) ? $p['slug'] : '' ) ) ] = $p;
	}
	$budget = $limit > 0 ? $limit : PHP_INT_MAX;
	while ( $budget > 0 && 'done' !== $state['phase'] ) {
		switch ( $state['phase'] ) {
			case 'settings':
				gcmn_ensure_functional_pages();
				gcmn_import_settings( $data, $force );
				$state['phase'] = 'pages';
				$state['offset'] = 0;
				$budget--;
				break;
			case 'pages':
				if ( $state['offset'] >= count( $pages ) ) {
					$state['phase'] = 'items';
					$state['offset'] = 0;
					break;
				}
				$state['counts']['pages'] += gcmn_import_page( $pages[ $state['offset'] ], $media_dir, $force, $report );
				$state['offset']++;
				$budget--;
				break;
			case 'items':
				if ( $state['offset'] >= count( $items ) ) {
					$state['phase'] = 'layouts';
					$state['offset'] = 0;
					$state['layouts_total'] = gcmn_import_pending_count();
					break;
				}
				$state['counts']['items'] += gcmn_import_item( $items[ $state['offset'] ], $media_dir, $force, $report );
				$state['offset']++;
				$budget--;
				break;
			case 'layouts':
				$lid = gcmn_import_next_layout();
				if ( ! $lid ) {
					$state['phase'] = 'menus';
					break;
				}
				$key = get_post_meta( $lid, '_gcmn_import_key', true );
				if ( isset( $by_path[ $key ] ) ) {
					gcmn_apply_layout( $lid, $by_path[ $key ], $media_dir );
				}
				delete_post_meta( $lid, '_gcmn_layout_pending' );
				$state['offset']++;
				$budget--;
				break;
			case 'menus':
				$state['counts']['menus'] += gcmn_import_menus( $data, $force );
				$state['phase'] = 'finish';
				$budget--;
				break;
			case 'finish':
				gcmn_ensure_parts( $force ); // the header and footer, built from the menus just imported (kept if already there)
				if ( ! empty( $data['redirects'] ) && is_array( $data['redirects'] ) ) {
					$clean = array();
					foreach ( $data['redirects'] as $from => $to ) {
						if ( is_string( $from ) && is_string( $to ) && 0 === strpos( $to, '/' ) ) {
							$clean[ sanitize_text_field( $from ) ] = sanitize_text_field( $to );
						}
					}
					update_option( 'gcmn_redirects', $clean, false );
				}
				if ( ! get_option( 'permalink_structure' ) ) {
					update_option( 'permalink_structure', '/%postname%/' ); // the pages live at readable addresses
				}
				flush_rewrite_rules();
				$state['phase'] = 'done';
				$budget--;
				break;
		}
	}
	$np = max( 1, count( $pages ) );
	$ni = max( 1, count( $items ) );
	$nl = max( 1, isset( $state['layouts_total'] ) ? $state['layouts_total'] : 1 );
	switch ( $state['phase'] ) {
		case 'settings':
			$percent = 1;
			break;
		case 'pages':
			$percent = 2 + (int) ( 40 * $state['offset'] / $np );
			break;
		case 'items':
			$percent = 42 + (int) ( 20 * $state['offset'] / $ni );
			break;
		case 'layouts':
			$percent = 62 + (int) ( 33 * min( 1, $state['offset'] / $nl ) );
			break;
		case 'menus':
		case 'finish':
			$percent = 97;
			break;
		default:
			$percent = 100;
	}
	return array( 'state' => $state, 'done' => 'done' === $state['phase'], 'percent' => $percent, 'report' => $report );
}

/** Import everything in one go (WP-CLI and tests). Returns array( pages, items, menus, skipped ). */
function gcmn_import_data( array $data, $media_dir = '', $force = false ) {
	$r = gcmn_import_run( $data, $media_dir, $force );
	$c = $r['state']['counts'];
	return array( 'pages' => $c['pages'], 'items' => $c['items'], 'menus' => $c['menus'], 'skipped' => array_slice( $r['report']['skipped'], 0, 50 ) );
}

if ( defined( 'WP_CLI' ) && WP_CLI ) {
	WP_CLI::add_command( 'gcmn import', function ( $args, $assoc ) {
		$r = gcmn_import_file( $args[0], isset( $assoc['media'] ) ? $assoc['media'] : '' );
		if ( is_wp_error( $r ) ) {
			WP_CLI::error( $r->get_error_message() );
		}
		update_option( 'gcmn_content_imported', GCMN_VERSION );
		WP_CLI::success( sprintf( 'Imported %d pages, %d items and %d menus.', $r['pages'], $r['items'], $r['menus'] ) );
		foreach ( $r['skipped'] as $s ) {
			WP_CLI::warning( 'Skipped ' . $s );
		}
	} );
}

/** The menus are saved per theme. When the GCMN theme is switched on, attach the imported menus to its locations. */
add_action( 'after_switch_theme', function () {
	$saved = get_option( 'gcmn_menu_ids', array() );
	if ( $saved ) {
		$locs = get_theme_mod( 'nav_menu_locations', array() );
		set_theme_mod( 'nav_menu_locations', array_merge( is_array( $locs ) ? $locs : array(), $saved ) );
	}
} );

/**
 * Loading the content that ships with the plugin (content/gcmn-content.json and its images).
 * It is done from the admin, in small steps with a progress bar, so a slow host cannot leave the site half built.
 * It starts by itself the first time an administrator opens the dashboard after the plugin is installed or updated,
 * and it never overwrites anything that was edited.
 */
function gcmn_bundle() {
	static $data = null;
	if ( null === $data ) {
		$file = GCMN_DIR . 'content/gcmn-content.json';
		$data = is_readable( $file ) ? json_decode( (string) file_get_contents( $file ), true ) : array(); // phpcs:ignore WordPress.WP.AlternativeFunctions.file_get_contents_file_get_contents
		$data = is_array( $data ) ? $data : array();
	}
	return $data;
}

function gcmn_import_needed() {
	return ! ( defined( 'GCMN_SKIP_BUNDLED_IMPORT' ) && GCMN_SKIP_BUNDLED_IMPORT ) && gcmn_bundle() && get_option( 'gcmn_content_imported' ) !== GCMN_VERSION;
}

/** Import everything now (used by the "start again" button and WP-CLI). */
function gcmn_import_bundled( $force = false ) {
	if ( ! $force && ! gcmn_import_needed() ) {
		return false;
	}
	$r = gcmn_import_run( gcmn_bundle(), GCMN_DIR . 'content/media', $force );
	if ( $r['done'] ) {
		update_option( 'gcmn_content_imported', GCMN_VERSION );
		delete_option( 'gcmn_import_state' );
	}
	return $r;
}

add_action( 'wp_ajax_gcmn_import_step', function () {
	if ( ! current_user_can( 'manage_options' ) || ! isset( $_POST['n'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['n'] ) ), 'gcmn_import_step' ) ) {
		wp_send_json_error( 'Not allowed.', 403 );
	}
	$force = ! empty( $_POST['force'] );
	$state = get_option( 'gcmn_import_state' );
	if ( ! empty( $_POST['restart'] ) ) {
		$state = null;
	}
	$r = gcmn_import_run( gcmn_bundle(), GCMN_DIR . 'content/media', $force, is_array( $state ) ? $state : null, 12 );
	if ( $r['done'] ) {
		update_option( 'gcmn_content_imported', GCMN_VERSION );
		delete_option( 'gcmn_import_state' );
	} else {
		update_option( 'gcmn_import_state', $r['state'], false );
	}
	wp_send_json_success( array( 'done' => $r['done'], 'percent' => $r['percent'], 'phase' => $r['state']['phase'], 'pages' => $r['state']['counts']['pages'], 'items' => $r['state']['counts']['items'], 'skipped' => $r['report']['skipped'] ) );
} );

add_action( 'admin_notices', function () {
	if ( ! current_user_can( 'manage_options' ) || ! gcmn_import_needed() ) {
		return;
	}
	$n = wp_create_nonce( 'gcmn_import_step' );
	?>
	<div class="notice notice-info" id="gcmn-import" style="padding:14px 18px">
		<p><strong>GCMN:</strong> loading the website content: pages, stories, ministries, menus, header and footer. Please keep this page open until it finishes. Nothing you have edited is overwritten.</p>
		<div style="background:#e6eaf3;border-radius:8px;height:14px;max-width:520px;overflow:hidden"><div id="gcmn-bar" style="background:#223C70;height:14px;width:0;transition:width .3s"></div></div>
		<p id="gcmn-msg" style="margin-top:8px">Starting…</p>
		<p><button type="button" class="button" id="gcmn-retry" style="display:none">Try again</button></p>
	</div>
	<script>
	(function () {
		var url = <?php echo wp_json_encode( admin_url( 'admin-ajax.php' ) ); ?>, nonce = <?php echo wp_json_encode( $n ); ?>;
		var bar = document.getElementById('gcmn-bar'), msg = document.getElementById('gcmn-msg'), retry = document.getElementById('gcmn-retry');
		var words = { settings: 'Settings', pages: 'Pages', items: 'Stories and ministries', layouts: 'Building the pages', menus: 'Menus', finish: 'Header and footer', done: 'Done' };
		function step() {
			var body = new URLSearchParams({ action: 'gcmn_import_step', n: nonce });
			fetch(url, { method: 'POST', credentials: 'same-origin', body: body }).then(function (r) { return r.json(); }).then(function (j) {
				if (!j.success) { throw new Error('refused'); }
				var d = j.data;
				bar.style.width = d.percent + '%';
				msg.textContent = (words[d.phase] || 'Working') + ' … ' + d.percent + '%';
				if (d.done) {
					msg.textContent = 'Done. The website content is loaded.';
					setTimeout(function () { location.reload(); }, 1200);
				} else { step(); }
			}).catch(function () {
				msg.textContent = 'The host stopped the loading. Press Try again; it carries on where it stopped.';
				retry.style.display = '';
			});
		}
		retry.addEventListener('click', function () { retry.style.display = 'none'; msg.textContent = 'Continuing…'; step(); });
		step();
	})();
	</script>
	<?php
} );

/** The "start again" form on the Website system menu uses the same steps; WP-CLI does it in one go. */
add_action( 'admin_post_gcmn_import_now', function () {
	if ( ! current_user_can( 'manage_options' ) || ! isset( $_POST['gcmn_import_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_import_nonce'] ) ), 'gcmn_import_now' ) ) {
		wp_die( 'Not allowed.', 403 );
	}
	delete_option( 'gcmn_content_imported' );
	delete_option( 'gcmn_import_state' );
	wp_safe_redirect( admin_url( 'index.php' ) );
	exit;
} );

/** Replace [[img:file.jpg|alt text]] in imported text with the picture from the media library. */
function gcmn_import_tokens( $html, $media_dir, $post_id ) {
	return preg_replace_callback( '/\[\[img:([^|\]]+)\|?([^\]]*)\]\]/', function ( $m ) use ( $media_dir, $post_id ) {
		$att = gcmn_import_media( $m[1], $media_dir, $post_id );
		if ( ! $att ) {
			return '';
		}
		if ( $m[2] ) {
			update_post_meta( $att, '_wp_attachment_image_alt', sanitize_text_field( html_entity_decode( $m[2] ) ) );
		}
		return '<figure class="g-fig">' . wp_get_attachment_image( $att, 'large' ) . '</figure>';
	}, $html );
}
