<?php
defined( 'ABSPATH' ) || exit;

/** Enquiry topics, from the Contact section of the Website Implementation System: appropriate enquiry channels. */
function gcmn_enquiry_topics() {
	return array(
		'general'     => 'A general question',
		'partnership' => 'Partnership',
		'giving'      => 'Giving and receipts',
		'serve'       => 'Serve or join staff',
		'prayer'      => 'Prayer',
		'story'       => 'Share a story',
		'mentor'      => 'Talk to a mentor',
		'internship'  => 'Internship application',
		'reference'   => 'Internship reference',
	);
}

add_action( 'init', function () {
	register_post_type( 'gcmn_enquiry', array(
		'labels'          => array( 'name' => 'Enquiries', 'singular_name' => 'Enquiry', 'not_found' => 'No enquiries yet' ),
		'public'          => false,
		'show_ui'         => true,
		'show_in_menu'    => true,
		'menu_icon'       => 'dashicons-email-alt',
		'menu_position'   => 22,
		'supports'        => array( 'title', 'editor' ),
		'capability_type' => 'gcmn_enquiry',
		'map_meta_cap'    => true,
		'capabilities'    => array(
			'edit_post' => 'gcmn_manage_enquiries', 'read_post' => 'gcmn_manage_enquiries', 'delete_post' => 'gcmn_manage_enquiries',
			'edit_posts' => 'gcmn_manage_enquiries', 'edit_others_posts' => 'gcmn_manage_enquiries', 'delete_posts' => 'gcmn_manage_enquiries',
			'publish_posts' => 'gcmn_manage_enquiries', 'read_private_posts' => 'gcmn_manage_enquiries', 'delete_private_posts' => 'gcmn_manage_enquiries',
			'delete_others_posts' => 'gcmn_manage_enquiries', 'edit_private_posts' => 'gcmn_manage_enquiries', 'edit_published_posts' => 'gcmn_manage_enquiries',
			'delete_published_posts' => 'gcmn_manage_enquiries', 'create_posts' => 'do_not_allow',
		),
	) );
} );

add_filter( 'manage_gcmn_enquiry_posts_columns', function ( $c ) {
	return array( 'cb' => $c['cb'], 'title' => 'Enquiry', 'gcmn_topic' => 'Topic', 'gcmn_email' => 'Email', 'gcmn_handled' => 'Handled', 'date' => 'Date' );
} );
add_action( 'manage_gcmn_enquiry_posts_custom_column', function ( $col, $id ) {
	if ( 'gcmn_topic' === $col ) {
		$t = gcmn_enquiry_topics();
		$k = get_post_meta( $id, '_gcmn_topic', true );
		echo esc_html( isset( $t[ $k ] ) ? $t[ $k ] : $k );
	} elseif ( 'gcmn_email' === $col ) {
		echo esc_html( get_post_meta( $id, '_gcmn_email', true ) );
	} elseif ( 'gcmn_handled' === $col ) {
		echo get_post_meta( $id, '_gcmn_handled', true ) ? 'Yes' : 'No';
	}
}, 10, 2 );

add_action( 'add_meta_boxes_gcmn_enquiry', function () {
	add_meta_box( 'gcmn_enq', 'Follow-up', function ( $post ) {
		wp_nonce_field( 'gcmn_enq', 'gcmn_enq_nonce' );
		echo '<p>From: ' . esc_html( get_post_meta( $post->ID, '_gcmn_name', true ) ) . ' &lt;' . esc_html( get_post_meta( $post->ID, '_gcmn_email', true ) ) . '&gt;</p>';
		echo '<label><input type="checkbox" name="gcmn_handled" value="1" ' . checked( get_post_meta( $post->ID, '_gcmn_handled', true ), '1', false ) . '> A person has replied</label>';
	}, 'gcmn_enquiry', 'side' );
} );
add_action( 'save_post_gcmn_enquiry', function ( $id ) {
	if ( isset( $_POST['gcmn_enq_nonce'] ) && wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_enq_nonce'] ) ), 'gcmn_enq' ) && current_user_can( 'gcmn_manage_enquiries' ) ) {
		empty( $_POST['gcmn_handled'] ) ? delete_post_meta( $id, '_gcmn_handled' ) : update_post_meta( $id, '_gcmn_handled', '1' );
	}
} );

/** Who receives an enquiry on this topic: the routing line for it, the giving email for giving, or the Content Editor. */
function gcmn_recipient_for( $topic ) {
	foreach ( gcmn_lines( gcmn_opt( 'routing' ) ) as $line ) {
		$p = gcmn_parts( $line, 2 );
		if ( strtolower( $p[0] ) === $topic && is_email( $p[1] ) ) {
			return $p[1];
		}
	}
	if ( 'giving' === $topic && is_email( gcmn_opt( 'giving_email' ) ) ) {
		return gcmn_opt( 'giving_email' );
	}
	return gcmn_editor_email();
}

/** Shortcode [gcmn_contact] (topic chooser) or [gcmn_contact topic="prayer" mentors="1" button="Send my request" label="Your prayer request"]. */
add_shortcode( 'gcmn_contact', function ( $atts = array() ) {
	$atts   = shortcode_atts( array( 'topic' => '', 'mentors' => '', 'button' => 'Send message', 'label' => 'Message' ), $atts, 'gcmn_contact' );
	$topics = gcmn_enquiry_topics();
	$fixed  = isset( $topics[ $atts['topic'] ] ) ? $atts['topic'] : '';
	$asked  = isset( $_GET['topic'] ) ? sanitize_key( wp_unslash( $_GET['topic'] ) ) : 'general'; // phpcs:ignore WordPress.Security.NonceVerification
	$asked  = $fixed ?: ( isset( $topics[ $asked ] ) ? $asked : 'general' );
	$mentors = $atts['mentors'] ? gcmn_mentors() : array();
	ob_start();
	if ( isset( $_GET['gcmn_sent'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification
		echo '<p class="gcmn-notice gcmn-ok" role="status">Thank you. We have your message and a person will reply by email.</p>';
	} elseif ( isset( $_GET['gcmn_err'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification
		echo '<p class="gcmn-notice gcmn-bad" role="alert">' . esc_html( rawurldecode( sanitize_text_field( wp_unslash( $_GET['gcmn_err'] ) ) ) ) . '</p>'; // phpcs:ignore WordPress.Security.NonceVerification
	}
	?>
	<form class="gcmn-form" method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
		<input type="hidden" name="action" value="gcmn_enquiry">
		<?php wp_nonce_field( 'gcmn_enquiry', 'gcmn_nonce' ); ?>
		<?php if ( $fixed ) : ?>
			<input type="hidden" name="topic" value="<?php echo esc_attr( $fixed ); ?>">
		<?php else : ?>
		<label>What is this about?
			<select name="topic"><?php foreach ( $topics as $k => $l ) : ?><option value="<?php echo esc_attr( $k ); ?>" <?php selected( $asked, $k ); ?>><?php echo esc_html( $l ); ?></option><?php endforeach; ?></select></label>
		<?php endif; ?>
		<?php if ( $mentors ) : ?>
		<label>Choose a mentor
			<select name="mentor" required><option value="">Choose</option><?php foreach ( $mentors as $m ) : ?><option><?php echo esc_html( $m['name'] ); ?></option><?php endforeach; ?></select></label>
		<?php endif; ?>
		<div class="gcmn-two">
			<label>Your name <input type="text" name="name" autocomplete="name" maxlength="100" required></label>
			<label>Email <input type="email" name="email" autocomplete="email" maxlength="150" required></label>
		</div>
		<label><?php echo esc_html( $atts['label'] ); ?> <textarea name="message" rows="6" maxlength="3000" required></textarea></label>
		<label class="gcmn-check"><input type="checkbox" name="consent" value="1" required> I agree that GCMN may use my details to reply to this message.</label>
		<p class="gcmn-hp" aria-hidden="true"><label>Leave empty <input type="text" name="website" tabindex="-1" autocomplete="off"></label></p>
		<button type="submit" class="gcmn-btn"><?php echo esc_html( $atts['button'] ); ?></button>
	</form>
	<?php
	return ob_get_clean();
} );

function gcmn_enquiry_back( $arg, $val ) {
	$to = wp_get_referer() ?: home_url( '/' );
	wp_safe_redirect( add_query_arg( $arg, $val, remove_query_arg( array( 'gcmn_sent', 'gcmn_err' ), $to ) ) );
	exit;
}

function gcmn_handle_enquiry() {
	if ( ! isset( $_POST['gcmn_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['gcmn_nonce'] ) ), 'gcmn_enquiry' ) ) {
		gcmn_enquiry_back( 'gcmn_err', rawurlencode( 'The page was open too long. Please try again.' ) );
	}
	if ( ! empty( $_POST['website'] ) ) {
		gcmn_enquiry_back( 'gcmn_sent', 1 ); // A bot filled the hidden field: pretend success, store nothing.
	}
	$ip   = isset( $_SERVER['REMOTE_ADDR'] ) ? sanitize_text_field( wp_unslash( $_SERVER['REMOTE_ADDR'] ) ) : '';
	$key  = 'gcmn_rl_' . md5( $ip );
	$seen = (int) get_transient( $key );
	if ( $seen >= 5 ) {
		gcmn_enquiry_back( 'gcmn_err', rawurlencode( 'Too many messages. Please wait a little and try again.' ) );
	}
	$topics  = gcmn_enquiry_topics();
	$topic   = isset( $_POST['topic'] ) ? sanitize_key( wp_unslash( $_POST['topic'] ) ) : 'general';
	$name    = isset( $_POST['name'] ) ? sanitize_text_field( wp_unslash( $_POST['name'] ) ) : '';
	$email   = isset( $_POST['email'] ) ? sanitize_email( wp_unslash( $_POST['email'] ) ) : '';
	$message = isset( $_POST['message'] ) ? sanitize_textarea_field( wp_unslash( $_POST['message'] ) ) : '';
	if ( ! isset( $topics[ $topic ] ) || '' === $name || ! is_email( $email ) || '' === $message || empty( $_POST['consent'] ) ) {
		gcmn_enquiry_back( 'gcmn_err', rawurlencode( 'Please fill in your name, a valid email and a message, and tick the box.' ) );
	}
	set_transient( $key, $seen + 1, HOUR_IN_SECONDS );
	$id = wp_insert_post( array(
		'post_type'    => 'gcmn_enquiry',
		'post_status'  => 'private',
		'post_title'   => $topics[ $topic ] . ': ' . $name,
		'post_content' => $message,
	) );
	if ( $id && ! is_wp_error( $id ) ) {
		update_post_meta( $id, '_gcmn_topic', $topic );
		update_post_meta( $id, '_gcmn_name', $name );
		update_post_meta( $id, '_gcmn_email', $email );
	}
	$to     = gcmn_recipient_for( $topic );
	$mentor = isset( $_POST['mentor'] ) ? sanitize_text_field( wp_unslash( $_POST['mentor'] ) ) : '';
	foreach ( gcmn_mentors() as $m ) {
		if ( $mentor && $m['name'] === $mentor ) {
			$to = $m['email'];
			update_post_meta( $id, '_gcmn_mentor', $mentor );
		}
	}
	wp_mail(
		$to,
		'Website enquiry: ' . $topics[ $topic ],
		"From: {$name} <{$email}>\nTopic: {$topics[$topic]}\n\n{$message}\n",
		array( 'Reply-To: ' . $name . ' <' . $email . '>' )
	);
	gcmn_enquiry_back( 'gcmn_sent', 1 );
}
add_action( 'admin_post_nopriv_gcmn_enquiry', 'gcmn_handle_enquiry' );
add_action( 'admin_post_gcmn_enquiry', 'gcmn_handle_enquiry' );
