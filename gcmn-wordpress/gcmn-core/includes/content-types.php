<?php
defined( 'ABSPATH' ) || exit;

add_action( 'init', 'gcmn_register_content_types' );

/**
 * The content types in the Website Implementation System: strategies, stories and testimonies, resources, prayer, partnership
 * opportunities and events. News, ministry updates and staff updates are ordinary posts in three categories.
 */
function gcmn_register_content_types() {
	$common = array(
		'public'       => true,
		'show_in_rest' => true,
		'menu_icon'    => 'dashicons-admin-post',
		'supports'     => array( 'title', 'editor', 'excerpt', 'thumbnail', 'revisions' ),
	);
	$types = array(
		'gcmn_strategy'    => array( 'Strategies', 'Strategy', 'strategies', 'dashicons-networking' ),
		'gcmn_story'       => array( 'Stories', 'Story', 'stories', 'dashicons-format-quote' ),
		'gcmn_event'       => array( 'Events', 'Event', 'events', 'dashicons-calendar-alt' ),
		'gcmn_resource'    => array( 'Resources', 'Resource', 'resources', 'dashicons-media-document' ),
		'gcmn_prayer'      => array( 'Prayer needs', 'Prayer need', 'prayer', 'dashicons-heart' ),
		'gcmn_opportunity' => array( 'Opportunities', 'Opportunity', 'partner/opportunities', 'dashicons-groups' ),
	);
	foreach ( $types as $slug => $t ) {
		register_post_type( $slug, array_merge( $common, array(
			'labels'      => array(
				'name'               => $t[0],
				'singular_name'      => $t[1],
				'add_new_item'       => 'Add ' . strtolower( $t[1] ),
				'edit_item'          => 'Edit ' . strtolower( $t[1] ),
				'search_items'       => 'Search ' . strtolower( $t[0] ),
				'not_found'          => 'None yet',
			),
			'has_archive' => $t[2],
			'rewrite'     => array( 'slug' => $t[2], 'with_front' => false ),
			'menu_icon'   => $t[3],
			'menu_position' => 21,
		) ) );
	}
}

/** Public detail fields for each type: key => array( input type, label, help ). Stored as post meta, prefixed with _gcmn_. */
function gcmn_detail_fields( $post_type ) {
	$cta = array(
		'cta_label' => array( 'text', 'Button text', 'For example "Read the report". Leave empty for no button.' ),
		'cta_url'   => array( 'url', 'Button link', '' ),
	);
	$related = array( 'strategy' => array( 'strategy', 'Strategy', 'Shown with this item and used to list it on the strategy page.' ) );
	switch ( $post_type ) {
		case 'gcmn_strategy':
			return array(
				'locations' => array( 'text', 'Where we work', 'For example the states or campuses.' ),
				'contact'   => array( 'text', 'Public contact for this strategy', 'Name and email or phone, as it should be shown. Only with the person’s consent.' ),
			) + $cta;
		case 'gcmn_story':
			return $related + array(
				'person'  => array( 'text', 'Person or place', 'Name and context, as the person agreed to be shown.' ),
				'consent' => array( 'checkbox', 'The people in this story have agreed in writing to it being published.', '' ),
			);
		case 'gcmn_event':
			return $related + array(
				'start'    => array( 'date', 'Starts', '' ),
				'end'      => array( 'date', 'Ends', 'Leave empty for a one-day event. The event leaves the site the day after it ends.' ),
				'location' => array( 'text', 'Location', '' ),
				'contact'  => array( 'text', 'Contact person', '' ),
			) + $cta;
		case 'gcmn_resource':
			return $related + array(
				'url'    => array( 'media', 'File or link', 'Choose a file from the library or paste a link.' ),
				'format' => array( 'text', 'Format', 'For example PDF, video or article.' ),
			);
		case 'gcmn_prayer':
			return $related + array(
				'expires' => array( 'date', 'Show until', 'The need leaves the site after this date. Empty means three weeks after publishing.' ),
			);
		case 'gcmn_opportunity':
			return $related + array(
				'ask'     => array( 'text', 'The need', 'One line, for example what is being asked for.' ),
				'expires' => array( 'date', 'Closes', 'The opportunity leaves the site after this date.' ),
				'contact' => array( 'text', 'Contact person', '' ),
			) + $cta;
		case 'post':
			return $related + array(
				'location' => array( 'text', 'Location', '' ),
			) + $cta;
	}
	return array();
}

add_action( 'add_meta_boxes', function () {
	foreach ( array_merge( array_filter( gcmn_workflow_types(), function ( $t ) { return 'page' !== $t; } ) ) as $type ) {
		if ( gcmn_detail_fields( $type ) ) {
			add_meta_box( 'gcmn_details', 'Details', 'gcmn_render_details', $type, 'normal', 'high' );
		}
	}
} );

function gcmn_render_details( $post ) {
	wp_nonce_field( 'gcmn_details', 'gcmn_details_nonce' );
	echo '<table class="form-table" role="presentation">';
	foreach ( gcmn_detail_fields( $post->post_type ) as $key => $f ) {
		$val = get_post_meta( $post->ID, '_gcmn_' . $key, true );
		$id  = 'gcmn_d_' . $key;
		echo '<tr><th scope="row"><label for="' . esc_attr( $id ) . '">' . ( 'checkbox' === $f[0] ? '' : esc_html( $f[1] ) ) . '</label></th><td>';
		switch ( $f[0] ) {
			case 'checkbox':
				echo '<label><input type="checkbox" id="' . esc_attr( $id ) . '" name="gcmn_d[' . esc_attr( $key ) . ']" value="1" ' . checked( $val, '1', false ) . '> ' . esc_html( $f[1] ) . '</label>';
				break;
			case 'strategy':
				echo '<select id="' . esc_attr( $id ) . '" name="gcmn_d[' . esc_attr( $key ) . ']"><option value="">None</option>';
				foreach ( get_posts( array( 'post_type' => 'gcmn_strategy', 'numberposts' => 100, 'orderby' => 'title', 'order' => 'ASC', 'post_status' => 'publish' ) ) as $s ) {
					echo '<option value="' . (int) $s->ID . '" ' . selected( (int) $val, $s->ID, false ) . '>' . esc_html( $s->post_title ) . '</option>';
				}
				echo '</select>';
				break;
			case 'media':
				echo '<input class="regular-text gcmn-media" type="url" id="' . esc_attr( $id ) . '" name="gcmn_d[' . esc_attr( $key ) . ']" value="' . esc_attr( $val ) . '"> <button type="button" class="button gcmn-pick" data-target="' . esc_attr( $id ) . '">Choose file</button>';
				break;
			default:
				$type = in_array( $f[0], array( 'date', 'url' ), true ) ? $f[0] : 'text';
				echo '<input class="regular-text" type="' . esc_attr( $type ) . '" id="' . esc_attr( $id ) . '" name="gcmn_d[' . esc_attr( $key ) . ']" value="' . esc_attr( $val ) . '">';
		}
		if ( $f[2] ) {
			echo '<p class="description">' . esc_html( $f[2] ) . '</p>';
		}
		echo '</td></tr>';
	}
	echo '</table>';
}

add_action( 'save_post', function ( $post_id, $post ) {
	if ( ! isset( $_POST['gcmn_details_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_details_nonce'] ) ), 'gcmn_details' ) ) {
		return;
	}
	if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE || ! current_user_can( 'edit_post', $post_id ) ) {
		return;
	}
	$in = isset( $_POST['gcmn_d'] ) && is_array( $_POST['gcmn_d'] ) ? wp_unslash( $_POST['gcmn_d'] ) : array();
	foreach ( gcmn_detail_fields( $post->post_type ) as $key => $f ) {
		$raw = isset( $in[ $key ] ) ? $in[ $key ] : '';
		switch ( $f[0] ) {
			case 'url':
			case 'media':
				$val = esc_url_raw( $raw );
				break;
			case 'checkbox':
				$val = $raw ? '1' : '';
				break;
			case 'strategy':
				$val = absint( $raw ) ?: '';
				break;
			case 'date':
				$val = preg_match( '/^\d{4}-\d{2}-\d{2}$/', (string) $raw ) ? $raw : '';
				break;
			default:
				$val = sanitize_text_field( $raw );
		}
		'' === $val ? delete_post_meta( $post_id, '_gcmn_' . $key ) : update_post_meta( $post_id, '_gcmn_' . $key, $val );
	}
}, 10, 2 );

add_action( 'admin_enqueue_scripts', function ( $hook ) {
	if ( in_array( $hook, array( 'post.php', 'post-new.php' ), true ) ) {
		wp_enqueue_media();
		$js = <<<'JS'
jQuery(function ($) {
	$('.gcmn-pick').on('click', function () {
		var target = $('#' + $(this).data('target'));
		var frame = wp.media({ multiple: false });
		frame.on('select', function () {
			target.val(frame.state().get('selection').first().toJSON().url);
		});
		frame.open();
	});
});
JS;
		wp_add_inline_script( 'jquery-core', $js );
	}
} );

/** Related strategy of a post, or null. */
function gcmn_strategy_of( $post_id ) {
	$id = (int) get_post_meta( $post_id, '_gcmn_strategy', true );
	$p  = $id ? get_post( $id ) : null;
	return ( $p && 'publish' === $p->post_status ) ? $p : null;
}

/** Order archives sensibly: events by start date, others newest first. */
add_action( 'pre_get_posts', function ( $q ) {
	if ( is_admin() || ! $q->is_main_query() ) {
		return;
	}
	if ( $q->is_post_type_archive( 'gcmn_event' ) ) {
		$q->set( 'meta_key', '_gcmn_start' );
		$q->set( 'orderby', 'meta_value' );
		$q->set( 'order', 'ASC' );
	}
	if ( $q->is_post_type_archive( 'gcmn_strategy' ) ) {
		$q->set( 'orderby', 'title' );
		$q->set( 'order', 'ASC' );
		$q->set( 'posts_per_page', 60 );
	}
	if ( $q->is_post_type_archive( array( 'gcmn_prayer', 'gcmn_opportunity', 'gcmn_resource', 'gcmn_story' ) ) ) {
		$q->set( 'posts_per_page', 18 );
	}
} );
