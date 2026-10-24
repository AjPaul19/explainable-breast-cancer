<?php
/** One content card, shared by every grid. Prints only what the item actually has. */
defined( 'ABSPATH' ) || exit;
$post = isset( $args['post'] ) ? $args['post'] : get_post();
if ( ! $post ) {
	return;
}
$type  = $post->post_type;
$label = '';
$line  = '';
if ( 'gcmn_event' === $type ) {
	$label = gcmn_t_event_dates( $post->ID );
	$line  = get_post_meta( $post->ID, '_gcmn_location', true );
} elseif ( 'gcmn_resource' === $type ) {
	$label = get_post_meta( $post->ID, '_gcmn_format', true );
} elseif ( 'gcmn_opportunity' === $type ) {
	$line = get_post_meta( $post->ID, '_gcmn_ask', true );
} elseif ( 'gcmn_story' === $type ) {
	$line = get_post_meta( $post->ID, '_gcmn_person', true );
} elseif ( in_array( $type, array( 'post', 'gcmn_prayer' ), true ) ) {
	$label = get_the_date( 'j F Y', $post );
}
$cats = 'post' === $type ? get_the_category( $post->ID ) : array();
$excerpt = has_excerpt( $post ) ? get_the_excerpt( $post ) : wp_trim_words( wp_strip_all_tags( strip_shortcodes( $post->post_content ) ), 24, '…' );
$accent = array( 'gcmn_strategy' => 'navy', 'gcmn_story' => 'green', 'gcmn_event' => 'orange', 'gcmn_resource' => 'blue', 'gcmn_prayer' => 'yellow', 'gcmn_opportunity' => 'blue', 'post' => 'navy' );
?>
<article class="card card-<?php echo esc_attr( isset( $accent[ $type ] ) ? $accent[ $type ] : 'navy' ); ?> reveal">
	<a class="card-link" href="<?php echo esc_url( get_permalink( $post ) ); ?>">
		<?php if ( has_post_thumbnail( $post ) ) : ?>
			<div class="card-img"><?php echo get_the_post_thumbnail( $post, 'gcmn-card', array( 'loading' => 'lazy', 'alt' => '' ) ); ?></div>
		<?php endif; ?>
		<div class="card-body">
			<?php if ( $label || $cats ) : ?><p class="chip"><?php echo esc_html( $label ?: $cats[0]->name ); ?></p><?php endif; ?>
			<h3><?php echo esc_html( get_the_title( $post ) ); ?></h3>
			<?php if ( $line ) : ?><p class="card-line"><?php echo esc_html( $line ); ?></p><?php endif; ?>
			<?php if ( $excerpt ) : ?><p class="card-text"><?php echo esc_html( $excerpt ); ?></p><?php endif; ?>
		</div>
	</a>
</article>
