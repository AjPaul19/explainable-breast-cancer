<?php
defined( 'ABSPATH' ) || exit;

/** Where a call to action leads. Keys are the choices on the submission form. */
function gcmn_cta_choices() {
	return array( 'read' => 'Read more', 'pray' => 'Pray', 'give' => 'Give', 'go' => 'Go', 'serve' => 'Serve', 'contact' => 'Contact us' );
}

/** Resolve a call-to-action key to a URL on this site, or '' when that page does not exist (the button is then simply not shown). */
function gcmn_cta_url( $key, $post_id = 0 ) {
	$page = function ( array $slugs ) {
		foreach ( $slugs as $slug ) {
			$p = get_page_by_path( $slug );
			if ( $p && 'publish' === $p->post_status ) {
				return get_permalink( $p );
			}
		}
		return '';
	};
	switch ( $key ) {
		case 'read':
			return $post_id ? get_permalink( $post_id ) : '';
		case 'pray':
			return get_post_type_archive_link( 'gcmn_prayer' ) ?: '';
		case 'give':
			return $page( array( 'giving', 'give' ) );
		case 'go':
		case 'serve':
			return $page( array( 'serve', 'serve-join-staff', 'join-staff', 'serve-and-join-staff' ) );
		case 'contact':
			return $page( array( 'contact' ) );
	}
	return '';
}

add_shortcode( 'gcmn_submit', function () {
	if ( ! is_user_logged_in() || ! current_user_can( 'gcmn_submit_content' ) ) {
		return '<div class="gcmn-form"><p>This form is for GCMN staff. <a href="' . esc_url( wp_login_url( get_permalink() ) ) . '">Sign in</a> to submit content.</p></div>';
	}
	$types = gcmn_submission_types();
	ob_start();
	if ( isset( $_GET['gcmn_sent'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification
		echo '<p class="gcmn-notice gcmn-ok" role="status">Thank you. Your submission is with the Content Editor for review.</p>';
	} elseif ( isset( $_GET['gcmn_err'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification
		echo '<p class="gcmn-notice gcmn-bad" role="alert">' . esc_html( rawurldecode( sanitize_text_field( wp_unslash( $_GET['gcmn_err'] ) ) ) ) . '</p>'; // phpcs:ignore WordPress.Security.NonceVerification
	}
	?>
	<form class="gcmn-form" method="post" enctype="multipart/form-data" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
		<input type="hidden" name="action" value="gcmn_submit">
		<?php wp_nonce_field( 'gcmn_submit', 'gcmn_nonce' ); ?>
		<label>Department or strategy
			<select name="dept" required><option value="">Choose</option>
			<?php foreach ( array_keys( gcmn_departments() ) as $d ) : ?><option><?php echo esc_html( $d ); ?></option><?php endforeach; ?>
			</select></label>
		<label>Content type
			<select name="kind" required><option value="">Choose</option>
			<?php foreach ( $types as $k => $t ) : ?><option value="<?php echo esc_attr( $k ); ?>"><?php echo esc_html( $t['label'] ); ?></option><?php endforeach; ?>
			</select></label>
		<label>Content title <input type="text" name="title" maxlength="140" required></label>
		<div class="gcmn-field"><label for="gcmn-body">Main content or story</label>
			<?php
			wp_editor( '', 'gcmn-body', array( 'textarea_name' => 'body', 'textarea_rows' => 10, 'media_buttons' => false, 'quicktags' => false, 'teeny' => true,
				'tinymce' => array( 'toolbar1' => 'bold,italic,bullist,numlist,blockquote,link,unlink,undo,redo', 'toolbar2' => '', 'block_formats' => 'Paragraph=p;Heading=h2;Subheading=h3' ) ) );
			?>
			<small>Write plainly. Use bold, lists and links where they help. State facts, names and numbers you can verify.</small></div>
		<div class="gcmn-two">
			<label>Date <input type="date" name="when"></label>
			<label>Location <input type="text" name="where" maxlength="140"></label>
		</div>
		<label>Relevant statistics <textarea name="stats" rows="3"></textarea>
			<small>Each number needs what it counts, the date and the source.</small></label>
		<label>Photos <input type="file" name="photos[]" accept="image/jpeg,image/png,image/webp" multiple>
			<small>Original photos only, up to 8 and 5 MB each. People in them must have agreed.</small></label>
		<label>Videos and links <textarea name="links" rows="3"></textarea><small>One web address per line.</small></label>
		<div class="gcmn-two">
			<label>Contact person <input type="text" name="contact" maxlength="140"></label>
			<label>Desired publication date <input type="date" name="desired"></label>
		</div>
		<div class="gcmn-two">
			<label>Approval required from
				<select name="approval"><option value="none">None needed</option><option value="strategy">Strategy leader</option><option value="leadership">Leadership</option><option value="finance">Finance</option></select></label>
			<label>Call to action
				<select name="cta"><?php foreach ( gcmn_cta_choices() as $k => $l ) : ?><option value="<?php echo esc_attr( $k ); ?>"><?php echo esc_html( $l ); ?></option><?php endforeach; ?></select></label>
		</div>
		<label class="gcmn-check"><input type="checkbox" name="sensitive" value="1"> This contains sensitive or restricted information that needs special handling (for example security, children or personal details).</label>
		<p class="gcmn-hp" aria-hidden="true"><label>Leave empty <input type="text" name="website" tabindex="-1" autocomplete="off"></label></p>
		<button type="submit" class="gcmn-btn">Submit for review</button>
	</form>
	<?php
	return ob_get_clean();
} );

function gcmn_submit_fail( $msg ) {
	wp_safe_redirect( add_query_arg( 'gcmn_err', rawurlencode( $msg ), wp_get_referer() ?: home_url( '/' ) ) );
	exit;
}

add_action( 'admin_post_gcmn_submit', function () {
	if ( ! isset( $_POST['gcmn_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_nonce'] ) ), 'gcmn_submit' ) || ! current_user_can( 'gcmn_submit_content' ) ) {
		wp_die( 'You are not allowed to submit content.', 403 );
	}
	if ( ! empty( $_POST['website'] ) ) {
		wp_safe_redirect( add_query_arg( 'gcmn_sent', 1, wp_get_referer() ?: home_url( '/' ) ) );
		exit;
	}
	$types = gcmn_submission_types();
	$kind  = isset( $_POST['kind'] ) ? sanitize_key( wp_unslash( $_POST['kind'] ) ) : '';
	$dept  = isset( $_POST['dept'] ) ? sanitize_text_field( wp_unslash( $_POST['dept'] ) ) : '';
	$title = isset( $_POST['title'] ) ? sanitize_text_field( wp_unslash( $_POST['title'] ) ) : '';
	$body  = isset( $_POST['body'] ) ? trim( wp_kses( wp_unslash( $_POST['body'] ), gcmn_rich_tags() ) ) : '';
	if ( ! isset( $types[ $kind ] ) || '' === $title || '' === trim( wp_strip_all_tags( $body ) ) ) {
		gcmn_submit_fail( 'Please choose a content type and fill in the title and the main content.' );
	}
	if ( ! array_key_exists( $dept, gcmn_departments() ) ) {
		gcmn_submit_fail( 'Please choose your department or strategy.' );
	}
	$t = $types[ $kind ];

	$html = wpautop( $body );
	$stats = isset( $_POST['stats'] ) ? sanitize_textarea_field( wp_unslash( $_POST['stats'] ) ) : '';
	if ( $stats ) {
		$html .= '<h3>In numbers</h3>' . wpautop( esc_html( $stats ) );
	}
	$links = array();
	foreach ( gcmn_lines( isset( $_POST['links'] ) ? sanitize_textarea_field( wp_unslash( $_POST['links'] ) ) : '' ) as $l ) {
		$u = esc_url_raw( $l, array( 'http', 'https' ) );
		if ( $u ) {
			$links[] = '<li><a href="' . esc_url( $u ) . '">' . esc_html( $u ) . '</a></li>';
		}
	}
	if ( $links ) {
		$html .= '<ul>' . implode( '', $links ) . '</ul>';
	}

	$post_id = wp_insert_post( array(
		'post_type'    => $t['type'],
		'post_status'  => 'pending',
		'post_title'   => $title,
		'post_content' => $html,
		'post_author'  => get_current_user_id(),
	), true );
	if ( is_wp_error( $post_id ) ) {
		gcmn_submit_fail( 'Sorry, that could not be saved. Please try again.' );
	}
	update_post_meta( $post_id, '_gcmn_via_form', '1' );
	if ( $t['cat'] ) {
		$term = get_term_by( 'name', $t['cat'], 'category' );
		if ( $term ) {
			wp_set_post_categories( $post_id, array( (int) $term->term_id ) );
		}
	}
	$meta = array(
		'dept'         => $dept,
		'approval'     => isset( $_POST['approval'] ) && in_array( $_POST['approval'], array( 'none', 'strategy', 'leadership', 'finance' ), true ) ? sanitize_key( wp_unslash( $_POST['approval'] ) ) : 'none',
		'sensitive'    => ! empty( $_POST['sensitive'] ) ? '1' : '',
		'location'     => isset( $_POST['where'] ) ? sanitize_text_field( wp_unslash( $_POST['where'] ) ) : '',
		'contact'      => isset( $_POST['contact'] ) ? sanitize_text_field( wp_unslash( $_POST['contact'] ) ) : '',
		'cta_key'      => isset( $_POST['cta'] ) && array_key_exists( $_POST['cta'], gcmn_cta_choices() ) ? sanitize_key( wp_unslash( $_POST['cta'] ) ) : 'read',
		'desired_date' => isset( $_POST['desired'] ) && preg_match( '/^\d{4}-\d{2}-\d{2}$/', wp_unslash( $_POST['desired'] ) ) ? wp_unslash( $_POST['desired'] ) : '',
	);
	$when = isset( $_POST['when'] ) && preg_match( '/^\d{4}-\d{2}-\d{2}$/', wp_unslash( $_POST['when'] ) ) ? wp_unslash( $_POST['when'] ) : '';
	if ( 'gcmn_event' === $t['type'] && $when ) {
		$meta['start'] = $when;
		$meta['end']   = $when;
	}
	foreach ( $meta as $k => $v ) {
		if ( '' !== $v ) {
			update_post_meta( $post_id, '_gcmn_' . $k, $v );
		}
	}

	// Photos: images only, size-limited, attached to the new item.
	if ( ! empty( $_FILES['photos']['name'][0] ) ) {
		require_once ABSPATH . 'wp-admin/includes/image.php';
		require_once ABSPATH . 'wp-admin/includes/file.php';
		require_once ABSPATH . 'wp-admin/includes/media.php';
		$first = true;
		$gallery = '';
		$count = min( 8, count( $_FILES['photos']['name'] ) );
		for ( $i = 0; $i < $count; $i++ ) {
			if ( UPLOAD_ERR_OK !== (int) $_FILES['photos']['error'][ $i ] || (int) $_FILES['photos']['size'][ $i ] > 5 * MB_IN_BYTES ) {
				continue;
			}
			$check = wp_check_filetype_and_ext( $_FILES['photos']['tmp_name'][ $i ], sanitize_file_name( $_FILES['photos']['name'][ $i ] ), array( 'jpg|jpeg' => 'image/jpeg', 'png' => 'image/png', 'webp' => 'image/webp' ) );
			if ( empty( $check['type'] ) ) {
				continue;
			}
			$_FILES['gcmn_one'] = array(
				'name'     => $_FILES['photos']['name'][ $i ],
				'type'     => $_FILES['photos']['type'][ $i ],
				'tmp_name' => $_FILES['photos']['tmp_name'][ $i ],
				'error'    => $_FILES['photos']['error'][ $i ],
				'size'     => $_FILES['photos']['size'][ $i ],
			);
			$att = media_handle_upload( 'gcmn_one', $post_id );
			if ( is_wp_error( $att ) ) {
				continue;
			}
			update_post_meta( $att, '_wp_attachment_image_alt', sanitize_text_field( $title ) );
			if ( $first ) {
				set_post_thumbnail( $post_id, $att );
				$first = false;
			} else {
				$gallery .= '<figure>' . wp_get_attachment_image( $att, 'large' ) . '</figure>';
			}
		}
		if ( $gallery ) {
			wp_update_post( array( 'ID' => $post_id, 'post_content' => $html . $gallery ) );
		}
	}

	$kindlabel = $t['label'];
	wp_mail(
		gcmn_editor_email(),
		'New website submission: ' . $title,
		"A new {$kindlabel} was submitted by " . wp_get_current_user()->display_name . " for {$dept}.\n\nReview it: " . get_edit_post_link( $post_id, 'raw' ) . "\n"
	);
	wp_safe_redirect( add_query_arg( 'gcmn_sent', 1, wp_get_referer() ?: home_url( '/' ) ) );
	exit;
} );
