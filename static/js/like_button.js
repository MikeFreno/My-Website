'use strict';

const e = React.createElement;
const f = React.createElement;

class LikeButton extends React.Component {
  constructor(props) {
    super(props);
    this.state = { liked: false };
  }

  render() {
    if (this.state.liked) {
      return 'You liked this.';
    }

    return e(
      'button',
      { onClick: () => this.setState({ liked: true }) },
      'Like'
    );
  }
}
document.querySelectorAll('.like_button_container')
  .forEach(domContainer => {
    // Read the comment ID from a data-* attribute.
    const commentID = parseInt(domContainer.dataset.commentid);
    const root = ReactDOM.createRoot(domContainer);
    root.render(
      e(LikeButton, { commentID: commentID })
    );
  });


cons r = React.createElement;
class commentReplyForm extends React.Component {
    constructor(props) {
        super(props);
        this.state = { display: none};
        }
    }

document.querySelectorAll('.commentReplyForm')
  .forEach(domContainer => {
    // Read the comment ID from a data-* attribute.
    const commentID = parseInt(domContainer.dataset.commentid);
    const root = ReactDOM.createRoot(domContainer);
    root.render(
      r(commentReplyForm, { commentID: commentID })
    );
  });