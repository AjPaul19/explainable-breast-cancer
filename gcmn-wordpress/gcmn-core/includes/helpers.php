<?php
defined( 'ABSPATH' ) || exit;

/** One option array holds every GCMN setting (see settings.php). */
function gcmn_opt( $key, $default = '' ) {
	$all = get_option( 'gcmn_settings', array() );
	return ( is_array( $all ) && isset( $all[ $key ] ) && '' !== $all[ $key ] ) ? $all[ $key ] : $default;
}

/** Split a textarea setting into trimmed, non-empty lines. */
function gcmn_lines( $text ) {
	$out = array();
	foreach ( preg_split( '/\r\n|\r|\n/', (string) $text ) as $line ) {
		$line = trim( $line );
		if ( '' !== $line ) {
			$out[] = $line;
		}
	}
	return $out;
}

/** Split "a | b | c" into trimmed parts, padded to $n entries. */
function gcmn_parts( $line, $n = 0 ) {
	$parts = array_map( 'trim', explode( '|', (string) $line ) );
	return $n ? array_pad( $parts, $n, '' ) : $parts;
}

/**
 * The submission types the Website Implementation System defines, and where each one lands.
 * 'type' is the post type, 'cat' an optional News category, 'review' the default days until its next review.
 */
function gcmn_submission_types() {
	return array(
		'news'        => array( 'label' => 'News',                    'type' => 'post',            'cat' => 'News',            'review' => 90 ),
		'ministry'    => array( 'label' => 'Ministry update',         'type' => 'post',            'cat' => 'Ministry update', 'review' => 90 ),
		'staff'       => array( 'label' => 'Staff update',            'type' => 'post',            'cat' => 'Staff update',    'review' => 90 ),
		'testimony'   => array( 'label' => 'Testimony',               'type' => 'gcmn_story',      'cat' => '',                'review' => 90 ),
		'event'       => array( 'label' => 'Event',                   'type' => 'gcmn_event',      'cat' => '',                'review' => 30 ),
		'resource'    => array( 'label' => 'Resource',                'type' => 'gcmn_resource',   'cat' => '',                'review' => 90 ),
		'prayer'      => array( 'label' => 'Prayer request',          'type' => 'gcmn_prayer',     'cat' => '',                'review' => 7 ),
		'opportunity' => array( 'label' => 'Partnership opportunity', 'type' => 'gcmn_opportunity', 'cat' => '',               'review' => 30 ),
	);
}

/** Post types that go through the review workflow. */
function gcmn_workflow_types() {
	return array( 'post', 'page', 'gcmn_strategy', 'gcmn_story', 'gcmn_event', 'gcmn_resource', 'gcmn_prayer', 'gcmn_opportunity' );
}

/** Default number of days until a post's next review. */
function gcmn_default_review_days( $post_type ) {
	foreach ( gcmn_submission_types() as $t ) {
		if ( $t['type'] === $post_type ) {
			return (int) $t['review'];
		}
	}
	return 'page' === $post_type ? 180 : 90; // strategies and pages: quarterly or half-yearly, as set in the update rhythm.
}

/** Departments and strategies a piece of content can belong to: those in Settings plus the strategies on the site. name => owner email. */
function gcmn_departments() {
	$list = array();
	foreach ( gcmn_lines( gcmn_opt( 'departments' ) ) as $line ) {
		$p = gcmn_parts( $line, 3 );
		if ( $p[0] ) {
			$list[ $p[0] ] = is_email( $p[1] ) ? $p[1] : '';
		}
	}
	$strategies = get_posts( array( 'post_type' => 'gcmn_strategy', 'post_status' => array( 'publish', 'draft', 'pending' ), 'numberposts' => 100, 'orderby' => 'title', 'order' => 'ASC', 'suppress_filters' => true, 'gcmn_all' => true ) );
	foreach ( $strategies as $s ) {
		if ( ! isset( $list[ $s->post_title ] ) ) {
			$list[ $s->post_title ] = '';
		}
	}
	ksort( $list );
	return $list;
}

/** The people for one department: array( 'owner' => Content Owner email, 'leader' => strategy leader (approver) email ). */
function gcmn_dept_emails( $dept ) {
	foreach ( gcmn_lines( gcmn_opt( 'departments' ) ) as $line ) {
		$p = gcmn_parts( $line, 3 );
		if ( $p[0] === $dept ) {
			return array( 'owner' => is_email( $p[1] ) ? $p[1] : '', 'leader' => is_email( $p[2] ) ? $p[2] : '' );
		}
	}
	return array( 'owner' => '', 'leader' => '' );
}

/** An email from the People settings: webadmin, editor, oversight, leadership, finance or tech. Falls back to the site administrator. */
function gcmn_email( $role ) {
	$e = gcmn_opt( $role . '_email' );
	return is_email( $e ) ? $e : '';
}

function gcmn_webadmin_email() {
	return gcmn_email( 'webadmin' ) ?: get_option( 'admin_email' );
}

/** The editor's email: where submissions go. */
function gcmn_editor_email() {
	return gcmn_email( 'editor' ) ?: gcmn_webadmin_email();
}

/** Tags allowed in formatted text fields (introduction, mission, giving instructions, staff submissions). */
function gcmn_rich_tags() {
	return array(
		'p' => array(), 'br' => array(), 'strong' => array(), 'b' => array(), 'em' => array(), 'i' => array(), 'u' => array(),
		'ul' => array(), 'ol' => array(), 'li' => array(), 'blockquote' => array(), 'h2' => array(), 'h3' => array(), 'h4' => array(),
		'a' => array( 'href' => true, 'title' => true, 'target' => true, 'rel' => true ), 'hr' => array(),
	);
}

/** Safe formatted text for output. */
function gcmn_rich( $html ) {
	return wpautop( wp_kses( (string) $html, gcmn_rich_tags() ) );
}

/** Create a page if no page with this slug exists. Returns the page ID. */
function gcmn_ensure_page( $slug, $title, $content = '', $extra = array() ) {
	$existing = get_page_by_path( $slug );
	if ( $existing ) {
		return (int) $existing->ID;
	}
	$id = wp_insert_post( array_merge( array(
		'post_type'    => 'page',
		'post_status'  => 'publish',
		'post_title'   => $title,
		'post_name'    => $slug,
		'post_content' => $content,
	), $extra ) );
	return is_wp_error( $id ) ? 0 : (int) $id;
}

/** The pages the plugin itself needs. Content pages (Who we are, Giving, ...) come from the importer. */
function gcmn_ensure_functional_pages() {
	gcmn_remove_wp_defaults();
	$home = gcmn_ensure_page( 'home', 'Home' );
	$news = gcmn_ensure_page( 'news', 'News and updates' );
	gcmn_ensure_page( 'contact', 'Contact', '[gcmn_contact]' );
	gcmn_ensure_page( 'submit-content', 'Submit content', '[gcmn_submit]', array() ); // Published but gated: the form only shows to signed-in staff and the page is set to noindex.
	if ( $home && ! get_option( 'gcmn_front_set' ) ) {
		update_option( 'show_on_front', 'page' );
		update_option( 'page_on_front', $home );
		if ( $news ) {
			update_option( 'page_for_posts', $news );
		}
		update_option( 'gcmn_front_set', 1 );
	}
	foreach ( array( 'News', 'Ministry update', 'Staff update' ) as $cat ) {
		if ( ! term_exists( $cat, 'category' ) ) {
			wp_insert_term( $cat, 'category' );
		}
	}
}

/** Public-facing date like "12 March 2026". */
function gcmn_date( $ymd ) {
	$ts = strtotime( $ymd );
	return $ts ? wp_date( 'j F Y', $ts ) : '';
}

/** A fresh WordPress ships a sample post and page. Remove them, but only if nobody has edited them. */
function gcmn_remove_wp_defaults() {
	$hello = get_page_by_path( 'hello-world', OBJECT, 'post' );
	if ( $hello && 0 === strpos( $hello->post_content, '<!-- wp:paragraph -->' . "
" . '<p>Welcome to WordPress.' ) ) {
		wp_delete_post( $hello->ID, true );
	}
	$sample = get_page_by_path( 'sample-page' );
	if ( $sample && false !== strpos( $sample->post_content, 'This is an example page' ) ) {
		wp_delete_post( $sample->ID, true );
	}
}

/** Mentors named in Settings: "Name | email | focus". The email is never shown on the site. */
function gcmn_mentors() {
	$out = array();
	foreach ( gcmn_lines( gcmn_opt( 'mentors' ) ) as $line ) {
		$p = gcmn_parts( $line, 3 );
		if ( $p[0] && is_email( $p[1] ) ) {
			$out[] = array( 'name' => $p[0], 'email' => $p[1], 'focus' => $p[2] );
		}
	}
	return $out;
}

/** A published or draft page by its slug alone, wherever it sits in the page tree. */
function gcmn_page_by_slug( $slug ) {
	if ( false !== strpos( $slug, '/' ) ) {
		return get_page_by_path( $slug ) ?: null;
	}
	$found = get_posts( array( 'post_type' => 'page', 'name' => sanitize_title( $slug ), 'post_status' => array( 'publish', 'draft', 'pending', 'private' ), 'numberposts' => 1, 'suppress_filters' => true ) );
	return $found ? $found[0] : null;
}
