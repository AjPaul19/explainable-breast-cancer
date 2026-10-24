<?php
defined( 'ABSPATH' ) || exit;

/**
 * Search engine optimisation. Everything is built from the content itself; a field left empty is simply not output.
 * Each page can override its search title and description in the "Search appearance" box.
 */
function gcmn_seo_types() {
	return array_merge( array( 'page', 'post' ), array_values( gcmn_workflow_types() ) );
}

add_action( 'add_meta_boxes', function () {
	foreach ( gcmn_seo_types() as $type ) {
		add_meta_box( 'gcmn_seo', 'Search appearance', function ( $post ) {
			wp_nonce_field( 'gcmn_seo', 'gcmn_seo_nonce' );
			echo '<p><label for="gcmn_seo_title"><strong>Search title</strong></label><br><input type="text" id="gcmn_seo_title" name="gcmn_seo_title" class="widefat" maxlength="70" value="' . esc_attr( get_post_meta( $post->ID, '_gcmn_seo_title', true ) ) . '"></p>';
			echo '<p class="description">Up to about 60 characters. Leave empty to use the page title.</p>';
			echo '<p><label for="gcmn_seo_desc"><strong>Search description</strong></label><br><textarea id="gcmn_seo_desc" name="gcmn_seo_desc" class="widefat" rows="3" maxlength="200">' . esc_textarea( get_post_meta( $post->ID, '_gcmn_seo_desc', true ) ) . '</textarea></p>';
			echo '<p class="description">One or two plain sentences, up to about 155 characters. Leave empty to use the summary or the first words of the page.</p>';
		}, $type, 'normal', 'low' );
	}
} );

add_action( 'save_post', function ( $post_id ) {
	if ( ! isset( $_POST['gcmn_seo_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_seo_nonce'] ) ), 'gcmn_seo' ) || ! current_user_can( 'edit_post', $post_id ) || wp_is_post_revision( $post_id ) ) {
		return;
	}
	foreach ( array( 'title' => 'gcmn_seo_title', 'desc' => 'gcmn_seo_desc' ) as $k => $field ) {
		$v = isset( $_POST[ $field ] ) ? sanitize_text_field( wp_unslash( $_POST[ $field ] ) ) : '';
		'' === $v ? delete_post_meta( $post_id, '_gcmn_seo_' . $k ) : update_post_meta( $post_id, '_gcmn_seo_' . $k, $v );
	}
} );

/** The page's search title, if the editor wrote one. */
add_filter( 'document_title_parts', function ( $parts ) {
	if ( is_singular() ) {
		$t = get_post_meta( (int) get_queried_object_id(), '_gcmn_seo_title', true );
		if ( $t ) {
			$parts['title'] = $t;
		}
	}
	return $parts;
} );

/** Description for the current view, or ''. */
function gcmn_seo_description() {
	if ( is_singular() && ! is_front_page() ) {
		$p   = get_queried_object();
		$set = get_post_meta( $p->ID, '_gcmn_seo_desc', true );
		if ( $set ) {
			return $set;
		}
		if ( has_excerpt( $p ) ) {
			return wp_strip_all_tags( get_the_excerpt( $p ) );
		}
		return wp_trim_words( wp_strip_all_tags( strip_shortcodes( $p->post_content ) ), 28, '…' );
	}
	if ( is_front_page() ) {
		return wp_strip_all_tags( gcmn_opt( 'tagline' ) . ( gcmn_opt( 'intro' ) ? '. ' . wp_trim_words( wp_strip_all_tags( gcmn_opt( 'intro' ) ), 24, '…' ) : '' ) );
	}
	if ( is_post_type_archive() ) {
		$o = get_queried_object();
		return ! empty( $o->description ) ? $o->description : '';
	}
	return '';
}

/** Share image for the current view: the featured image, else the site logo. */
function gcmn_seo_image() {
	if ( is_singular() && has_post_thumbnail() ) {
		return get_the_post_thumbnail_url( null, 'large' );
	}
	return function_exists( 'gcmn_theme_logo_url' ) ? gcmn_theme_logo_url() : '';
}

function gcmn_seo_url() {
	if ( is_singular() ) {
		return get_permalink();
	}
	if ( is_post_type_archive() ) {
		return get_post_type_archive_link( get_query_var( 'post_type' ) );
	}
	return is_front_page() ? home_url( '/' ) : '';
}

function gcmn_seo_breadcrumb() {
	$items = array( array( 'Home', home_url( '/' ) ) );
	if ( is_singular() && ! is_front_page() ) {
		$p = get_queried_object();
		if ( 'page' === $p->post_type ) {
			foreach ( array_reverse( get_post_ancestors( $p ) ) as $a ) {
				$items[] = array( get_the_title( $a ), get_permalink( $a ) );
			}
		} elseif ( get_post_type_archive_link( $p->post_type ) ) {
			$o = get_post_type_object( $p->post_type );
			$items[] = array( $o->labels->name, get_post_type_archive_link( $p->post_type ) );
		}
		$items[] = array( get_the_title( $p ), get_permalink( $p ) );
	} elseif ( is_post_type_archive() ) {
		$o = get_queried_object();
		$items[] = array( $o->labels->name, get_post_type_archive_link( $o->name ) );
	}
	$list = array();
	foreach ( $items as $i => $it ) {
		$list[] = array( '@type' => 'ListItem', 'position' => $i + 1, 'name' => wp_strip_all_tags( $it[0] ), 'item' => $it[1] );
	}
	return array( '@type' => 'BreadcrumbList', '@id' => ( gcmn_seo_url() ?: home_url( '/' ) ) . '#breadcrumb', 'itemListElement' => $list );
}

function gcmn_seo_graph() {
	$home = home_url( '/' );
	$org  = array( '@type' => 'Organization', '@id' => $home . '#organization', 'name' => get_bloginfo( 'name' ), 'url' => $home );
	if ( function_exists( 'gcmn_theme_logo_url' ) ) {
		$org['logo'] = array( '@type' => 'ImageObject', 'url' => gcmn_theme_logo_url() );
	}
	$same = array();
	foreach ( array( 'facebook', 'instagram', 'x', 'youtube', 'linkedin' ) as $k ) {
		if ( gcmn_opt( $k ) ) {
			$same[] = gcmn_opt( $k );
		}
	}
	if ( $same ) {
		$org['sameAs'] = $same;
	}
	foreach ( array( 'email' => 'email', 'phone' => 'telephone' ) as $opt => $prop ) {
		if ( gcmn_opt( $opt ) ) {
			$org[ $prop ] = gcmn_opt( $opt );
		}
	}
	if ( gcmn_opt( 'address' ) ) {
		$org['address'] = array( '@type' => 'PostalAddress', 'streetAddress' => str_replace( "\n", ', ', gcmn_opt( 'address' ) ), 'addressCountry' => 'NG' );
	}
	$graph = array( $org, array( '@type' => 'WebSite', '@id' => $home . '#website', 'url' => $home, 'name' => get_bloginfo( 'name' ), 'publisher' => array( '@id' => $home . '#organization' ), 'inLanguage' => get_bloginfo( 'language' ) ) );
	$url   = gcmn_seo_url();
	$desc  = gcmn_seo_description();
	if ( is_singular() ) {
		$p    = get_queried_object();
		$slug = $p->post_name;
		$type = 'WebPage';
		if ( 'contact' === $slug ) {
			$type = 'ContactPage';
		} elseif ( in_array( $slug, array( 'who-we-are', 'our-history', 'our-values' ), true ) ) {
			$type = 'AboutPage';
		}
		$page = array( '@type' => $type, '@id' => $url . '#webpage', 'url' => $url, 'name' => wp_get_document_title(), 'isPartOf' => array( '@id' => $home . '#website' ), 'inLanguage' => get_bloginfo( 'language' ) );
		if ( $desc ) {
			$page['description'] = $desc;
		}
		$img = gcmn_seo_image();
		if ( is_singular() && has_post_thumbnail() ) {
			$page['primaryImageOfPage'] = array( '@type' => 'ImageObject', 'url' => $img );
		}
		$page['breadcrumb'] = array( '@id' => $url . '#breadcrumb' );
		$graph[] = $page;
		if ( in_array( $p->post_type, array( 'post', 'gcmn_story', 'gcmn_resource' ), true ) ) {
			$art = array(
				'@type' => 'post' === $p->post_type || 'gcmn_story' === $p->post_type ? 'Article' : 'CreativeWork',
				'@id' => $url . '#article', 'mainEntityOfPage' => array( '@id' => $url . '#webpage' ),
				'headline' => wp_strip_all_tags( get_the_title( $p ) ), 'datePublished' => get_the_date( 'c', $p ), 'dateModified' => get_the_modified_date( 'c', $p ),
				'publisher' => array( '@id' => $home . '#organization' ), 'author' => array( '@id' => $home . '#organization' ), 'inLanguage' => get_bloginfo( 'language' ),
			);
			if ( has_post_thumbnail() ) {
				$art['image'] = array( $img );
			}
			if ( $desc ) {
				$art['description'] = $desc;
			}
			$graph[] = $art;
		}
		if ( 'gcmn_event' === $p->post_type ) {
			$ev = array( '@type' => 'Event', '@id' => $url . '#event', 'name' => wp_strip_all_tags( get_the_title( $p ) ), 'url' => $url, 'organizer' => array( '@id' => $home . '#organization' ), 'eventAttendanceMode' => 'https://schema.org/OfflineEventAttendanceMode', 'eventStatus' => 'https://schema.org/EventScheduled' );
			$start = get_post_meta( $p->ID, '_gcmn_start', true );
			$end   = get_post_meta( $p->ID, '_gcmn_end', true );
			if ( $start ) {
				$ev['startDate'] = $start;
				if ( $end ) {
					$ev['endDate'] = $end;
				}
			}
			$loc = get_post_meta( $p->ID, '_gcmn_location', true );
			if ( $loc ) {
				$ev['location'] = array( '@type' => 'Place', 'name' => $loc, 'address' => $loc );
			}
			if ( $desc ) {
				$ev['description'] = $desc;
			}
			if ( has_post_thumbnail() ) {
				$ev['image'] = array( $img );
			}
			if ( $start ) { // an event without a date is not marked up
				$graph[] = $ev;
			}
		}
	} elseif ( is_front_page() ) {
		$graph[] = array( '@type' => 'WebPage', '@id' => $home . '#webpage', 'url' => $home, 'name' => wp_get_document_title(), 'isPartOf' => array( '@id' => $home . '#website' ) );
	}
	if ( ! is_front_page() && ( is_singular() || is_post_type_archive() ) ) {
		$graph[] = gcmn_seo_breadcrumb();
	}
	return array( '@context' => 'https://schema.org', '@graph' => $graph );
}

add_action( 'wp_head', function () {
	if ( is_404() || is_search() ) {
		return;
	}
	$desc = gcmn_seo_description();
	$url  = gcmn_seo_url();
	$img  = gcmn_seo_image();
	if ( $desc ) {
		echo '<meta name="description" content="' . esc_attr( $desc ) . '">' . "\n";
		echo '<meta property="og:description" content="' . esc_attr( $desc ) . '">' . "\n";
		echo '<meta name="twitter:description" content="' . esc_attr( $desc ) . '">' . "\n";
	}
	echo '<meta property="og:type" content="' . ( is_singular( array( 'post', 'gcmn_story' ) ) ? 'article' : 'website' ) . '">' . "\n";
	echo '<meta property="og:site_name" content="' . esc_attr( get_bloginfo( 'name' ) ) . '">' . "\n";
	echo '<meta property="og:locale" content="' . esc_attr( str_replace( '-', '_', get_bloginfo( 'language' ) ) ) . '">' . "\n";
	echo '<meta property="og:title" content="' . esc_attr( wp_get_document_title() ) . '">' . "\n";
	echo '<meta name="twitter:title" content="' . esc_attr( wp_get_document_title() ) . '">' . "\n";
	if ( $url ) {
		echo '<meta property="og:url" content="' . esc_url( $url ) . '">' . "\n";
	}
	if ( $img ) {
		echo '<meta property="og:image" content="' . esc_url( $img ) . '">' . "\n";
		echo '<meta name="twitter:image" content="' . esc_url( $img ) . '">' . "\n";
	}
	echo '<meta name="twitter:card" content="' . ( $img && is_singular() && has_post_thumbnail() ? 'summary_large_image' : 'summary' ) . '">' . "\n";
	echo '<script type="application/ld+json">' . wp_json_encode( gcmn_seo_graph(), JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE ) . '</script>' . "\n";
}, 5 );

/** WordPress already adds a canonical link and max-image-preview; keep the staff pages out of search. */
add_filter( 'wp_robots', function ( $robots ) {
	if ( is_404() ) {
		$robots['noindex'] = true;
	}
	if ( is_page( 'submit-content' ) ) {
		$robots['noindex']  = true;
		$robots['nofollow'] = true;
	}
	if ( is_singular() && get_post_meta( get_queried_object_id(), '_gcmn_noindex', true ) ) {
		$robots['noindex'] = true;
	}
	return $robots;
} );

/** Keep staff-only pages out of the public sitemap and add the content types people search for. */
add_filter( 'wp_sitemaps_posts_query_args', function ( $args, $type ) {
	if ( 'page' === $type ) {
		$args['post__not_in'] = array_merge( isset( $args['post__not_in'] ) ? $args['post__not_in'] : array(), array_filter( array( (int) get_option( 'gcmn_submit_page_id' ), ( $p = get_page_by_path( 'submit-content' ) ) ? $p->ID : 0 ) ) );
	}
	return $args;
}, 10, 2 );

add_filter( 'wp_sitemaps_post_types', function ( $types ) {
	unset( $types['gcmn_enquiry'], $types['gcmn_outbox'] );
	return $types;
} );

/** Every image needs words for people who cannot see it, and for search. */
add_filter( 'wp_get_attachment_image_attributes', function ( $attr, $att ) {
	if ( empty( $attr['alt'] ) ) {
		$parent = $att->post_parent ? get_the_title( $att->post_parent ) : '';
		$attr['alt'] = $att->post_title && ! preg_match( '/^(img|dsc|image|photo)[-_ 0-9]*$/i', $att->post_title ) ? $att->post_title : $parent;
	}
	return $attr;
}, 10, 2 );

/** Link the sitemap from robots.txt (WordPress adds this itself when the site is public). */
add_filter( 'robots_txt', function ( $output, $public ) {
	if ( $public && false === strpos( $output, 'Sitemap:' ) ) {
		$output .= "\nSitemap: " . home_url( '/wp-sitemap.xml' ) . "\n";
	}
	return $output;
}, 10, 2 );
