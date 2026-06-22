/// Core library for myplaceholder-project.
pub fn echo(input: &[u8]) -> Vec<u8> {
    input.to_vec()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn echo_roundtrip() {
        assert_eq!(echo(b"hello"), b"hello");
    }
}
