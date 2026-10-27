//! Execute existing Criterion closures once, preserving their measurement boundary.
pub use std::hint::black_box;

use gungraun::client_requests::callgrind;

pub enum BatchSize {
  PerIteration,
  SmallInput,
}

pub struct Criterion {
  pub entry: String,
  pub selected: Option<String>,
  pub cases: Vec<(String, String)>,
  pub measured: usize,
}

impl Criterion {
  pub fn bench_function(&mut self, name: impl AsRef<str>, mut routine: impl FnMut(&mut Bencher)) {
    let name = name.as_ref();
    self.cases.push((self.entry.clone(), name.to_owned()));
    if self.selected.as_deref() == Some(name) {
      let mut bencher = Bencher { iterations: 0 };
      routine(&mut bencher);
      assert_eq!(
        bencher.iterations, 1,
        "each case must measure exactly one iteration"
      );
      self.measured += 1;
    }
  }

  pub fn benchmark_group(&mut self, name: &str) -> BenchmarkGroup<'_> {
    BenchmarkGroup {
      criterion: self,
      name: name.to_owned(),
    }
  }
}

pub struct BenchmarkGroup<'a> {
  criterion: &'a mut Criterion,
  name: String,
}

impl BenchmarkGroup<'_> {
  pub fn bench_function(&mut self, name: impl AsRef<str>, routine: impl FnMut(&mut Bencher)) {
    self
      .criterion
      .bench_function(format!("{}/{}", self.name, name.as_ref()), routine);
  }

  pub fn finish(self) {}
}

pub struct Bencher {
  iterations: usize,
}

struct Measurement;

impl Measurement {
  fn start() -> Self {
    // Unlike a thread-local collection toggle, instrumentation applies to all threads.
    callgrind::start_instrumentation();
    Self
  }
}

impl Drop for Measurement {
  fn drop(&mut self) {
    callgrind::stop_instrumentation();
  }
}

impl Bencher {
  #[allow(clippy::iter_not_returning_iterator)] // Match Criterion's existing API.
  pub fn iter<R>(&mut self, mut routine: impl FnMut() -> R) {
    self.iterations += 1;
    // Match the steady-state semantics of Criterion's repeated iter calls,
    // including lazy CachedSource and module-code-generation state.
    drop(black_box(routine()));
    let measurement = Measurement::start();
    // Criterion's iter includes output destruction in the measured region.
    drop(black_box(routine()));
    drop(measurement);
  }

  pub fn iter_batched<I, R>(
    &mut self,
    mut setup: impl FnMut() -> I,
    mut routine: impl FnMut(I) -> R,
    _: BatchSize,
  ) {
    self.iterations += 1;
    let input = black_box(setup());
    let measurement = Measurement::start();
    let output = black_box(routine(input));
    drop(measurement);
    drop(output);
  }

  pub fn iter_batched_ref<I, R>(
    &mut self,
    mut setup: impl FnMut() -> I,
    mut routine: impl FnMut(&mut I) -> R,
    _: BatchSize,
  ) {
    self.iterations += 1;
    let mut input = black_box(setup());
    let measurement = Measurement::start();
    let output = black_box(routine(&mut input));
    drop(measurement);
    drop(output);
    drop(input);
  }
}
